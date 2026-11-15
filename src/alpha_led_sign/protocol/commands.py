"""Commands: one instruction inside a Packet, a Command Code plus its data."""

from abc import ABC, abstractmethod
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, time
from enum import Enum
from typing import ClassVar

from alpha_led_sign.protocol.addresses import check_sign_address
from alpha_led_sign.protocol.codes import Color, Control, CurrentTime, Font, Spacing, Speed, Wide
from alpha_led_sign.protocol.labels import check_file_label
from alpha_led_sign.protocol.memory import MemoryFile, RunTime, TextFile, lock_byte
from alpha_led_sign.protocol.message import (
    Message,
    Segment,
    decode_content,
    decode_message,
    encode_content,
    normalize_content,
)
from alpha_led_sign.protocol.pictures import DotsPicture, decode_dots_picture
from alpha_led_sign.protocol.response import ResponseError, ResponseItem, UnexpectedResponseError
from alpha_led_sign.protocol.versions import ProtocolVersion


class Command(ABC):
    """One Command. Subclasses set ``code`` and implement ``encode_data``."""

    code: ClassVar[str]
    """The one-character Command Code (Table 6, p. 11)."""

    @property
    def pause_after(self) -> float:
        """Seconds of silence the Sign needs after this Command before it can take more data."""
        return 0.0

    def pauses_in_data(self) -> tuple[tuple[int, float], ...]:
        """Silences the Sign needs inside the Data Field: (offset into the data, seconds)."""
        return ()

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
        for file in files[:-1]:
            if isinstance(file, TextFile) and file.size == 0:
                # p. 27, note 1: size 0 takes the rest of memory, so it must come last.
                raise ValueError(
                    f"TEXT File {file.label!r} has size 0, which only the last File may have"
                )
        object.__setattr__(self, "files", tuple(files))

    def encode_payload(self) -> bytes:
        return b"".join(file.encode() for file in self.files)


@dataclass(frozen=True)
class ClearMemory(SpecialFunction):
    """Erase every File and the Memory Configuration ("$" with no data, p. 21)."""

    label: ClassVar[str] = "$"


@dataclass(frozen=True, init=False)
class SetRunTimes(SpecialFunction):
    """Set when TEXT Files run each day (")", p. 22). Other Files keep their Run Times.

    Writing it ends a Priority TEXT File (p. 20).
    """

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
    """Set the date (";", p. 26), sent as mmddyy.

    Only years 1997-2096 are accepted. p. 28, note 15 gives that window for the
    two-digit year on Alpha 2.0 and later only. It is applied to every Sign until a
    hardware check shows how an Alpha 1.0 Sign reads the year.
    """

    label: ClassVar[str] = ";"
    date: date

    def __post_init__(self) -> None:
        # p. 28, note 15 (Alpha 2.0 and later): two-digit years mean 1997-2096.
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
        order = self.order.value.encode("ascii")
        return order + lock_byte(self.locked) + "".join(self.labels).encode("ascii")


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
class SetSignAddress(SpecialFunction):
    """Set the Sign Address ("7", p. 26). A DIP switch address wins after a power cycle."""

    label: ClassVar[str] = "7"
    address: int

    def __post_init__(self) -> None:
        check_sign_address(self.address)

    def encode_payload(self) -> bytes:
        return f"{self.address:02X}".encode("ascii")


STRING_MAX_BYTES = 125
"""STRING File data is buffered, so it is limited to 125 bytes (p. 37)."""


def _allowed_in_string(segment: Segment) -> bool:
    """Table 19, p. 37: the Control Codes a STRING File may contain."""
    match segment:
        case str() | Speed() | Wide() | CurrentTime() | Font() | Spacing() | Control.NEW_LINE:
            return True
        case Color():
            return segment not in (Color.RAINBOW_1, Color.RAINBOW_2)
        case _:
            return False


@dataclass(frozen=True, init=False)
class WriteString(Command):
    """Write a STRING File (p. 37). Unlike a TEXT File write, the display does not blank."""

    code: ClassVar[str] = "G"
    label: str
    content: tuple[Segment, ...]

    def __init__(self, label: str, content: str | Sequence[Segment]) -> None:
        check_file_label(label)
        segments = normalize_content(content)
        for segment in segments:
            if not _allowed_in_string(segment):
                raise ValueError(f"{segment!r} cannot be used in a STRING File (Table 19, p. 37)")
        object.__setattr__(self, "label", label)
        object.__setattr__(self, "content", segments)
        size = len(encode_content(segments))
        if size > STRING_MAX_BYTES:
            raise ValueError(f"STRING File data is at most {STRING_MAX_BYTES} bytes, got {size}")

    def encode_data(self) -> bytes:
        return self.label.encode("ascii") + encode_content(self.content)

    def codes(self) -> Iterable[object]:
        return (segment for segment in self.content if not isinstance(segment, str))


DOTS_PICTURE_ROWS_PAUSE = 0.1
"""Seconds of silence a SMALL DOTS PICTURE write needs after its Width (p. 40)."""


@dataclass(frozen=True)
class WriteDotsPicture(Command):
    """Write a SMALL DOTS PICTURE File (Table 22, p. 39). The display blanks until it ends.

    The picture's height and width must match the File's entry in the Memory
    Configuration (p. 39).
    """

    code: ClassVar[str] = "I"
    label: str
    picture: DotsPicture

    def __post_init__(self) -> None:
        check_file_label(self.label)

    def encode_data(self) -> bytes:
        size = f"{self.label}{self.picture.height:02X}{self.picture.width:02X}"
        rows = b"".join(
            "".join(pixel.value for pixel in row).encode("ascii") + b"\r"
            for row in self.picture.rows
        )
        return size.encode("ascii") + rows

    def pauses_in_data(self) -> tuple[tuple[int, float], ...]:
        # p. 40: at least 100 ms after the Width, before the Row Bit Patterns.
        return ((len(self.label) + 4, DOTS_PICTURE_ROWS_PAUSE),)


class Read[T](Command):
    """A Command that asks the Sign for data. It must be the last Command in a Packet."""

    must_be_last: ClassVar[bool] = True

    @abstractmethod
    def parse(self, response: Sequence[ResponseItem]) -> T:
        """Turn the decoded Response into a value."""


def _find(response: Sequence[ResponseItem], code: str, prefix: str, what: str) -> bytes:
    """The data after ``prefix`` in the Response Command with ``code``."""
    for item in response:
        if item.code == code and item.data.startswith(prefix.encode("ascii")):
            return item.data[len(prefix) :]
    raise UnexpectedResponseError(f"the Response does not contain {what}: {response!r}")


@dataclass(frozen=True)
class ReadText(Read[Message]):
    """Read a TEXT File back as a Message (p. 19). The Sign answers with a Write TEXT."""

    code: ClassVar[str] = "B"
    label: str

    def __post_init__(self) -> None:
        check_file_label(self.label)

    def encode_data(self) -> bytes:
        return self.label.encode("ascii")

    def parse(self, response: Sequence[ResponseItem]) -> Message:
        return decode_message(_find(response, "A", self.label, f"TEXT File {self.label}"))


@dataclass(frozen=True)
class ReadString(Read[tuple[Segment, ...]]):
    """Read a STRING File's content (p. 38). The Sign answers with a Write STRING."""

    code: ClassVar[str] = "H"
    label: str

    def __post_init__(self) -> None:
        check_file_label(self.label)

    def encode_data(self) -> bytes:
        return self.label.encode("ascii")

    def parse(self, response: Sequence[ResponseItem]) -> tuple[Segment, ...]:
        return decode_content(_find(response, "G", self.label, f"STRING File {self.label}"))


@dataclass(frozen=True)
class ReadDotsPicture(Read[DotsPicture]):
    """Read a SMALL DOTS PICTURE File (Table 23, p. 41). The Sign answers with an "I"."""

    code: ClassVar[str] = "J"
    label: str

    def __post_init__(self) -> None:
        check_file_label(self.label)

    def encode_data(self) -> bytes:
        return self.label.encode("ascii")

    def parse(self, response: Sequence[ResponseItem]) -> DotsPicture:
        data = _find(response, "I", self.label, f"DOTS PICTURE File {self.label}")
        return decode_dots_picture(data)


class ReadSpecial[T](Read[T]):
    """A Read SPECIAL FUNCTION Command (Table 16, p. 29). The Sign answers with an "E"."""

    code: ClassVar[str] = "F"
    label: ClassVar[str]

    def encode_data(self) -> bytes:
        return self.label.encode("ascii")

    def _data(self, response: Sequence[ResponseItem]) -> bytes:
        return _find(response, "E", self.label, f"SPECIAL FUNCTION {self.label!r}")


@dataclass(frozen=True)
class ReadDayOfWeek(ReadSpecial[Weekday]):
    """Read the Sign's day of the week ("&", p. 30)."""

    label: ClassVar[str] = "&"

    def parse(self, response: Sequence[ResponseItem]) -> Weekday:
        return Weekday(self._data(response).decode("ascii"))


@dataclass(frozen=True)
class SerialErrorStatus:
    """The Serial Error Status Register (p. 31): errors since it was last cleared."""

    illegal_command: bool = False
    """An illegal Command Code, File Label, or SPECIAL FUNCTION."""
    checksum_error: bool = False
    buffer_overflow: bool = False
    timeout: bool = False
    framing_error: bool = False
    """Usually a baud rate mismatch."""
    parity_error: bool = False
    """Not used on most Signs."""

    @classmethod
    def decode(cls, bits: int) -> "SerialErrorStatus":
        """Decode the register byte (p. 31). Bit 6 is always set; bits 5-0 are errors."""
        return cls(
            illegal_command=bool(bits & 0x20),
            checksum_error=bool(bits & 0x10),
            buffer_overflow=bool(bits & 0x08),
            timeout=bool(bits & 0x04),
            framing_error=bool(bits & 0x02),
            parity_error=bool(bits & 0x01),
        )

    @property
    def ok(self) -> bool:
        """True if no error has been recorded."""
        return not any(
            (
                self.illegal_command,
                self.checksum_error,
                self.buffer_overflow,
                self.timeout,
                self.framing_error,
                self.parity_error,
            )
        )


@dataclass(frozen=True)
class ReadSerialErrorStatus(ReadSpecial[SerialErrorStatus]):
    """Read and reset the Serial Error Status Register ("*", p. 31)."""

    label: ClassVar[str] = "*"

    def parse(self, response: Sequence[ResponseItem]) -> SerialErrorStatus:
        data = self._data(response)
        if len(data) != 1:
            raise ResponseError(f"expected one Serial Error Status byte, got {data!r}")
        return SerialErrorStatus.decode(data[0])


@dataclass(frozen=True)
class GeneralInformation:
    """What Read General Information reports (p. 29). Mostly useful for troubleshooting."""

    firmware: str
    revision: str
    firmware_date: str
    """Release month and two-digit year, as "MMYY"."""
    time: time
    time_format: TimeFormat
    speaker_enabled: bool
    memory_total: int
    """Size of the Memory Pool in bytes."""
    memory_free: int
    """Unused part of the Memory Pool in bytes."""


_GENERAL_INFORMATION_LENGTH = 29  # FFFFFFFF f MmYy HhNn R SS POOL,pool


@dataclass(frozen=True)
class ReadGeneralInformation(ReadSpecial[GeneralInformation]):
    """Read firmware, clock, speaker, and memory details ('"', p. 29)."""

    label: ClassVar[str] = '"'

    def parse(self, response: Sequence[ResponseItem]) -> GeneralInformation:
        data = self._data(response)
        if data.startswith(b"\x00"):  # p. 29 note 1: only some Signs send it
            data = data[1:]
        text = data.decode("ascii", errors="replace")
        if len(text) != _GENERAL_INFORMATION_LENGTH or text[24] != ",":
            raise ResponseError(f"unexpected General Information format: {data!r}")
        return GeneralInformation(
            firmware=text[0:8],
            revision=text[8],
            firmware_date=text[9:13],
            time=time(int(text[13:15]), int(text[15:17])),
            time_format=TimeFormat(text[17]),
            speaker_enabled=text[18:20] == "00",
            memory_total=int(text[20:24], 16),
            memory_free=int(text[25:29], 16),
        )


@dataclass(frozen=True)
class NetworkQueryResponse:
    """One Sign's answer to a Network Query (p. 32)."""

    sign_type: str
    address: int
    errors: SerialErrorStatus


@dataclass(frozen=True)
class NetworkQuery(ReadSpecial[NetworkQueryResponse]):
    """Ask every Sign for its Sign Type, Sign Address, and serial errors ("-", p. 32).

    Broadcast it to address 0. Each Sign answers 1 s + 0.5 s x its address after the
    EOT, so one Packet brings many Responses; ``parse`` reads one of them.
    """

    label: ClassVar[str] = "-"

    def parse(self, response: Sequence[ResponseItem]) -> NetworkQueryResponse:
        data = self._data(response)
        if len(data) != 4:
            raise ResponseError(f"expected a 4-byte Network Query answer, got {data!r}")
        try:
            address = int(data[1:3].decode("ascii"), 16)
        except ValueError:
            raise ResponseError(f"bad Sign Address in Network Query answer {data!r}") from None
        return NetworkQueryResponse(chr(data[0]), address, SerialErrorStatus.decode(data[3]))
