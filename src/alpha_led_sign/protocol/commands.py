"""Commands: one instruction inside a Packet, a Command Code plus its data."""

from abc import ABC, abstractmethod
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, time
from enum import Enum
from typing import ClassVar

from alpha_led_sign.protocol.labels import check_file_label
from alpha_led_sign.protocol.memory import MemoryFile, RunTime
from alpha_led_sign.protocol.message import Message
from alpha_led_sign.protocol.versions import ProtocolVersion


class Command(ABC):
    """One Command. Subclasses set ``code`` and implement ``encode_data``."""

    code: ClassVar[str]
    """The one-character Command Code (Table 6, p. 11)."""

    @property
    def pause_after(self) -> float:
        """Seconds of silence the Sign needs after this Command before it can take more data."""
        return 0.0

    must_be_last: ClassVar[bool] = False
    """True if this Command may only be the last one in a nested Packet (p. 11)."""

    min_version: ClassVar[ProtocolVersion] = ProtocolVersion.EZ_KEY_II
    """The earliest Protocol Version that has this Command."""

    @abstractmethod
    def encode_data(self) -> bytes:
        """Return the Data Field that follows the Command Code."""

    def codes(self) -> Iterable[object]:
        """The Modes, Display Positions, and Control Codes in this Command's data."""
        return ()


PRIORITY_LABEL = "0"
"""The File Label of the Priority TEXT File (p. 20). Writing an empty Message to it clears it."""

PRIORITY_MAX_BYTES = 125
"""The Priority TEXT File's fixed size (p. 20)."""


@dataclass(frozen=True)
class WriteText(Command):
    """Write a Message to a TEXT File (p. 18). Writing blanks the display."""

    code: ClassVar[str] = "A"
    label: str
    message: Message

    def __post_init__(self) -> None:
        check_file_label(self.label)
        if self.label == PRIORITY_LABEL and len(self.message.encode()) > PRIORITY_MAX_BYTES:
            raise ValueError(
                f"the Priority TEXT File holds at most {PRIORITY_MAX_BYTES} bytes, "
                f"and this Message encodes to {len(self.message.encode())}"
            )

    def encode_data(self) -> bytes:
        return self.label.encode("ascii") + self.message.encode()

    def codes(self) -> Iterable[object]:
        return self.message.codes()


class SpecialFunction(Command):
    """A Write SPECIAL FUNCTION Command (Table 15, p. 21): a label and its data."""

    code: ClassVar[str] = "E"
    label: ClassVar[str]

    def encode_data(self) -> bytes:
        return self.label.encode("ascii") + self.encode_payload()

    def encode_payload(self) -> bytes:
        """The Special Functions Data that follows the label."""
        return b""


@dataclass(frozen=True)
class SetTime(SpecialFunction):
    """Set the time of day (" ", p. 21). Seconds are ignored."""

    label: ClassVar[str] = " "
    time: time

    def encode_payload(self) -> bytes:
        return f"{self.time.hour:02d}{self.time.minute:02d}".encode("ascii")


class TimeFormat(Enum):
    """How a Sign shows the time ("'", p. 22)."""

    AM_PM = "S"
    TWENTY_FOUR_HOUR = "M"


@dataclass(frozen=True)
class SetTimeFormat(SpecialFunction):
    """Choose 12-hour (am/pm) or 24-hour time ("'", p. 22)."""

    label: ClassVar[str] = "'"
    format: TimeFormat

    def encode_payload(self) -> bytes:
        return self.format.value.encode("ascii")


@dataclass(frozen=True, init=False)
class SetMemoryConfiguration(SpecialFunction):
    """Replace the Memory Configuration ("$", p. 21). This erases every File on the Sign."""

    label: ClassVar[str] = "$"
    files: tuple[MemoryFile, ...]

    def __init__(self, files: Sequence[MemoryFile]) -> None:
        if not files:
            raise ValueError("a Memory Configuration needs at least one File; use ClearMemory")
        object.__setattr__(self, "files", tuple(files))

    def encode_payload(self) -> bytes:
        return b"".join(file.encode() for file in self.files)


@dataclass(frozen=True)
class ClearMemory(SpecialFunction):
    """Erase every File and the Memory Configuration ("$" with no data, p. 21)."""

    label: ClassVar[str] = "$"


@dataclass(frozen=True, init=False)
class SetRunTimes(SpecialFunction):
    """Set when TEXT Files run each day (")", p. 22). Other Files keep their Run Times."""

    label: ClassVar[str] = ")"
    run_times: tuple[tuple[str, RunTime], ...]

    def __init__(self, run_times: Mapping[str, RunTime]) -> None:
        for file_label in run_times:
            check_file_label(file_label)
        object.__setattr__(self, "run_times", tuple(run_times.items()))

    def encode_payload(self) -> bytes:
        return b"".join(
            file_label.encode("ascii") + run_time.encode()
            for file_label, run_time in self.run_times
        )


@dataclass(frozen=True)
class SetDate(SpecialFunction):
    """Set the date (";", p. 26), sent as mmddyy."""

    label: ClassVar[str] = ";"
    date: date

    def __post_init__(self) -> None:
        # p. 28, note 15: two-digit years are windowed to 1997-2096.
        if not 1997 <= self.date.year <= 2096:
            raise ValueError(f"a Sign's date must be in 1997-2096, got {self.date.year}")

    def encode_payload(self) -> bytes:
        return self.date.strftime("%m%d%y").encode("ascii")


class Weekday(Enum):
    """Days of the week as the Sign numbers them ("&", p. 22)."""

    SUNDAY = "1"
    MONDAY = "2"
    TUESDAY = "3"
    WEDNESDAY = "4"
    THURSDAY = "5"
    FRIDAY = "6"
    SATURDAY = "7"

    @classmethod
    def of(cls, day: date) -> "Weekday":
        """The Weekday ``day`` falls on."""
        return cls(str(day.isoweekday() % 7 + 1))


@dataclass(frozen=True)
class SetDayOfWeek(SpecialFunction):
    """Set the day of the week ("&", p. 22). The Sign advances it at midnight."""

    label: ClassVar[str] = "&"
    day: Weekday

    def encode_payload(self) -> bytes:
        return self.day.value.encode("ascii")


class RunOrder(Enum):
    """How the Run Sequence picks the next TEXT File ("." K field, p. 23)."""

    BY_RUN_TIME = "T"
    """Run each File during its Run Time (the default)."""
    IN_ORDER = "S"
    """Run every File in order, ignoring Run Times."""
    DELETE_WHEN_DONE = "D"
    """Run each File during its Run Time, then delete it when its Stop Time passes."""


@dataclass(frozen=True, init=False)
class SetRunSequence(SpecialFunction):
    """Set the order the Sign shows TEXT Files in (".", p. 23)."""

    label: ClassVar[str] = "."
    labels: tuple[str, ...]
    order: RunOrder
    locked: bool

    def __init__(
        self,
        labels: Iterable[str],
        *,
        order: RunOrder = RunOrder.BY_RUN_TIME,
        locked: bool = False,
    ) -> None:
        labels = tuple(labels)
        if not 1 <= len(labels) <= 128:
            raise ValueError(f"a Run Sequence holds 1 to 128 TEXT Files, got {len(labels)}")
        for file_label in labels:
            check_file_label(file_label)
        object.__setattr__(self, "labels", labels)
        object.__setattr__(self, "order", order)
        object.__setattr__(self, "locked", locked)

    def encode_payload(self) -> bytes:
        lock = "L" if self.locked else "U"
        return (self.order.value + lock + "".join(self.labels)).encode("ascii")


class RunDay(Enum):
    """The first day (or set of days) a TEXT File runs ("2" S field, p. 24)."""

    DAILY = "0"
    SUNDAY = "1"
    MONDAY = "2"
    TUESDAY = "3"
    WEDNESDAY = "4"
    THURSDAY = "5"
    FRIDAY = "6"
    SATURDAY = "7"
    WEEKDAYS = "8"
    WEEKENDS = "9"
    ALWAYS = "A"
    NEVER = "B"


@dataclass(frozen=True)
class RunDays:
    """The days a TEXT File runs: from ``start`` to ``stop``.

    ``stop`` only matters when ``start`` is a single day; the Sign still needs a value.
    """

    start: RunDay
    stop: Weekday = Weekday.SUNDAY

    def encode(self) -> bytes:
        return (self.start.value + self.stop.value).encode("ascii")


@dataclass(frozen=True, init=False)
class SetRunDays(SpecialFunction):
    """Set which days TEXT Files run ("2", p. 24). Writing it ends a Priority TEXT File."""

    label: ClassVar[str] = "2"
    run_days: tuple[tuple[str, RunDays], ...]

    def __init__(self, run_days: Mapping[str, RunDays]) -> None:
        for file_label in run_days:
            check_file_label(file_label)
        object.__setattr__(self, "run_days", tuple(run_days.items()))

    def encode_payload(self) -> bytes:
        return b"".join(
            file_label.encode("ascii") + days.encode() for file_label, days in self.run_days
        )


@dataclass(frozen=True)
class SetSpeaker(SpecialFunction):
    """Enable or disable the Sign's speaker ("!", p. 21). Disabled by default."""

    label: ClassVar[str] = "!"
    enabled: bool

    def encode_payload(self) -> bytes:
        return b"00" if self.enabled else b"FF"


FIXED_TONE_PAUSE = 3.0
"""Seconds to wait after a fixed tone before sending more (p. 27, note 4)."""


class Tone(Enum):
    """The Sign's built-in tones ("(", p. 22)."""

    CONTINUOUS = "0"
    """A continuous tone for about 2 seconds."""
    THREE_BEEPS = "1"
    """Three short beeps, about 2 seconds in all."""


@dataclass(frozen=True)
class Beep(SpecialFunction):
    """Sound a built-in tone ("(", p. 22). It must be the last Command in a Packet."""

    label: ClassVar[str] = "("
    must_be_last: ClassVar[bool] = True
    tone: Tone

    @property
    def pause_after(self) -> float:
        return FIXED_TONE_PAUSE

    def encode_payload(self) -> bytes:
        return self.tone.value.encode("ascii")


@dataclass(frozen=True)
class ProgrammableTone(SpecialFunction):
    """Sound a tone of a given pitch and length ("(" + "2", p. 22).

    ``frequency`` is the speaker setting 0-254 (00H-FEH), ``duration`` is 1-15 tenths of
    a second, and ``repeats`` is 0-15. It must be the last Command in a Packet.
    """

    label: ClassVar[str] = "("
    must_be_last: ClassVar[bool] = True
    frequency: int
    duration: int
    repeats: int = 0

    def __post_init__(self) -> None:
        if not 0 <= self.frequency <= 0xFE:
            raise ValueError(f"tone frequency must be 0-254, got {self.frequency}")
        if not 1 <= self.duration <= 0xF:
            raise ValueError(f"tone duration must be 1-15 tenths of a second, got {self.duration}")
        if not 0 <= self.repeats <= 0xF:
            raise ValueError(f"tone repeats must be 0-15, got {self.repeats}")

    @property
    def pause_after(self) -> float:
        # p. 27 note 5: wait until the tone has finished. The manual doesn't say whether
        # "repeated" counts the first play, so assume it doesn't and wait the longer time.
        return self.duration * 0.1 * (self.repeats + 1)

    def encode_payload(self) -> bytes:
        return f"2{self.frequency:02X}{self.duration:X}{self.repeats:X}".encode("ascii")


@dataclass(frozen=True)
class SoftReset(SpecialFunction):
    """Restart the Sign through its power-up diagnostics, keeping memory (",", p. 22)."""

    label: ClassVar[str] = ","


@dataclass(frozen=True)
class ClearSerialErrorStatus(SpecialFunction):
    """Reset the Serial Error Status Register to 40H ("4", p. 24).

    Send it first in a nested Packet, and read the register last, to learn whether that
    Packet arrived intact.
    """

    label: ClassVar[str] = "4"


@dataclass(frozen=True)
class SetSerialAddress(SpecialFunction):
    """Set the Sign Address ("7", p. 26). A DIP switch address wins after a power cycle."""

    label: ClassVar[str] = "7"
    address: int

    def __post_init__(self) -> None:
        if not 0 <= self.address <= 0xFF:
            raise ValueError(f"a Sign Address must be 0-255, got {self.address}")

    def encode_payload(self) -> bytes:
        return f"{self.address:02X}".encode("ascii")
