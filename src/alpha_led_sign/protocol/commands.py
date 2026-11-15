"""Commands: one instruction inside a Packet, a Command Code plus its data."""

from abc import ABC, abstractmethod
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, time
from enum import Enum
from typing import ClassVar

from alpha_led_sign.protocol.addresses import check_sign_address
from alpha_led_sign.protocol.capabilities import Capability
from alpha_led_sign.protocol.control_codes import allowed_in_string_file
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
from alpha_led_sign.protocol.pictures import DotsPicture, PixelColor, decode_dots_picture
from alpha_led_sign.protocol.requirements import (
    TALL_FONTS,
    CapabilityRequirement,
    DisplaySizeRequirement,
    FontPositionRequirement,
    MemoryRequirement,
    Requirement,
    VersionRequirement,
    requires,
)
from alpha_led_sign.protocol.responses import ResponseError, ResponseItem, UnexpectedResponseError
from alpha_led_sign.protocol.versions import ProtocolVersion


@dataclass(frozen=True)
class Pause:
    """Silence the Sign needs at this point in a Command's data.

    A Command's ``encode_data`` returns one between two pieces of bytes, and the
    Packet encoder splits the Chunk there.

    Attributes:
        seconds: How long the line must stay quiet.
    """

    seconds: float


class Command(ABC):
    """One Command: a Command Code and its data.

    Subclass it to add a Command the library lacks: set ``code`` and implement
    ``encode_data``. The Packet encoder and validation need nothing else. Override
    ``codes`` or ``requirements`` so that validation sees what the Command needs.

    Attributes:
        code: The one-character Command Code (Table 6, p. 11).
        must_be_last: True if the Command may only be the last one in a nested Packet
            (p. 11), as reads and tones must.
        min_version: The earliest Protocol Version that has the Command.
    """

    code: ClassVar[str]

    @property
    def pause_after(self) -> float:
        """Seconds of silence the Sign needs after this Command before it can take more data."""
        return 0.0

    must_be_last: ClassVar[bool] = False

    min_version: ClassVar[ProtocolVersion] = ProtocolVersion.EZ_KEY_II

    @abstractmethod
    def encode_data(self) -> bytes | Sequence[bytes | Pause]:
        """Encode the Data Field that follows the Command Code.

        Returns:
            The data as bytes. A Command that needs the line quiet partway through
            its data returns it in pieces, with a Pause where each silence falls.
        """

    def codes(self) -> Iterable[object]:
        """List the Modes, Display Positions, and Control Codes in the Command's data.

        Returns:
            The codes, for validation. The default is none.
        """
        return ()

    def requirements(self) -> Iterator[Requirement]:
        """List what this Command needs from a Sign Model to be shown as written.

        A Command that needs more than the default, such as room in memory, adds to
        these.

        Yields:
            A VersionRequirement for ``min_version`` when it is later than EZ KEY II,
            then the Requirements of each of ``codes()``.
        """
        if self.min_version > ProtocolVersion.EZ_KEY_II:
            yield VersionRequirement(self.min_version, self)
        for code in self.codes():
            yield from requires(code)


PRIORITY_LABEL = "0"
"""The File Label of the Priority TEXT File (p. 20). Writing an empty Message to it clears it."""

PRIORITY_MAX_BYTES = 125
"""The Priority TEXT File's fixed size (p. 20)."""


@dataclass(frozen=True)
class WriteText(Command):
    """Write a Message to a TEXT File (p. 18). Writing blanks the display.

    Attributes:
        label: The TEXT File's File Label. ``PRIORITY_LABEL`` writes the Priority
            TEXT File.
        message: The content.

    Raises:
        ValueError: The File Label is invalid, or the Priority TEXT File's Message
            encodes to more than 125 bytes.
    """

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
        """Encode the File Label and the Message.

        Returns:
            The Data Field.
        """
        return self.label.encode("ascii") + self.message.encode()

    def codes(self) -> Iterable[object]:
        """List the Modes, Display Positions, and Control Codes in the Message.

        Returns:
            The codes, in order.
        """
        return self.message.codes()

    def requirements(self) -> Iterator[Requirement]:
        """List what this Command needs from a Sign Model.

        Yields:
            The base Requirements, then a FontPositionRequirement for each font taller
            than 7 rows in a Frame that has a Mode Field.
        """
        yield from super().requirements()
        for frame in self.message.frames:
            if frame.mode is None:
                continue  # no Mode Field, so no Display Position is sent
            for font in sorted(TALL_FONTS.intersection(frame.content), key=lambda f: f.value):
                yield FontPositionRequirement(font, frame.position)


class SpecialFunction(Command):
    """A Write SPECIAL FUNCTION Command (Table 15, p. 21): a label and its data.

    Subclasses set ``label`` and override ``encode_payload``.

    Attributes:
        label: The one-character Special Function label.
    """

    code: ClassVar[str] = "E"
    label: ClassVar[str]

    def encode_data(self) -> bytes:
        """Encode the Special Function label and its data.

        Returns:
            ``label`` followed by ``encode_payload()``.
        """
        return self.label.encode("ascii") + self.encode_payload()

    def encode_payload(self) -> bytes:
        """Encode the Special Functions Data that follows the label.

        Returns:
            The data. The default is empty.
        """
        return b""


@dataclass(frozen=True)
class SetTime(SpecialFunction):
    """Set the time of day (" ", p. 21). Seconds are ignored.

    Attributes:
        time: The time to set.
    """

    label: ClassVar[str] = " "
    time: time

    def encode_payload(self) -> bytes:
        """Encode the time as four digits, hhmm, in 24-hour time.

        Returns:
            The Special Functions Data.
        """
        return f"{self.time.hour:02d}{self.time.minute:02d}".encode("ascii")


class TimeFormat(Enum):
    """How a Sign shows the time ("'", p. 22).

    Attributes:
        AM_PM: 12-hour time with AM or PM.
        TWENTY_FOUR_HOUR: 24-hour time.
    """

    AM_PM = "S"
    TWENTY_FOUR_HOUR = "M"


@dataclass(frozen=True)
class SetTimeFormat(SpecialFunction):
    """Choose 12-hour (AM/PM) or 24-hour time ("'", p. 22).

    Attributes:
        format: The time format.
    """

    label: ClassVar[str] = "'"
    format: TimeFormat

    def encode_payload(self) -> bytes:
        """Encode the format as ``S`` (AM/PM) or ``M`` (24-hour).

        Returns:
            The Special Functions Data.
        """
        return self.format.value.encode("ascii")


@dataclass(frozen=True, init=False)
class SetMemoryConfiguration(SpecialFunction):
    """Replace the Memory Configuration ("$", p. 21). This erases every File on the Sign.

    Args:
        files: The Files the Sign should have.

    Attributes:
        files: The Files, in order.

    Raises:
        ValueError: ``files`` is empty, or a TEXT File other than the last has size
            0.
    """

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
        """Encode one entry for each File, in order.

        Returns:
            The Special Functions Data.
        """
        return b"".join(file.encode() for file in self.files)

    def requirements(self) -> Iterator[Requirement]:
        """List what this Command needs from a Sign Model.

        Yields:
            The base Requirements, then a MemoryRequirement for the Files.
        """
        yield from super().requirements()
        yield MemoryRequirement(self.files)


CLEAR_MEMORY_PAUSE = 1.5
"""Seconds a Sign needs after Clear Memory. Read sooner, a 4120C reported memory still
in use (docs/hardware-results.md, "Memory Configuration limit")."""


@dataclass(frozen=True)
class ClearMemory(SpecialFunction):
    """Erase every File and the Memory Configuration ("$" with no data, p. 21)."""

    label: ClassVar[str] = "$"

    @property
    def pause_after(self) -> float:
        """Seconds the Sign needs after Clear Memory: 1.5, measured on a 4120C."""
        return CLEAR_MEMORY_PAUSE


@dataclass(frozen=True, init=False)
class SetRunTimes(SpecialFunction):
    """Set when TEXT Files run each day (")", p. 22). Other Files keep their Run Times.

    Writing it ends a Priority TEXT File (p. 20).

    Args:
        run_times: A Run Time for each File Label.

    Attributes:
        run_times: The File Labels and Run Times, in order.

    Raises:
        ValueError: A File Label is invalid.
    """

    label: ClassVar[str] = ")"
    run_times: tuple[tuple[str, RunTime], ...]

    def __init__(self, run_times: Mapping[str, RunTime]) -> None:
        for file_label in run_times:
            check_file_label(file_label)
        object.__setattr__(self, "run_times", tuple(run_times.items()))

    def encode_payload(self) -> bytes:
        """Encode each File Label followed by its Run Time.

        Returns:
            The Special Functions Data.
        """
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

    Attributes:
        date: The date to set.

    Raises:
        ValueError: The year is outside 1997-2096.
    """

    label: ClassVar[str] = ";"
    date: date

    def __post_init__(self) -> None:
        # p. 28, note 15 (Alpha 2.0 and later): two-digit years mean 1997-2096.
        if not 1997 <= self.date.year <= 2096:
            raise ValueError(f"a Sign's date must be in 1997-2096, got {self.date.year}")

    def encode_payload(self) -> bytes:
        """Encode the date as mmddyy.

        Returns:
            The Special Functions Data.
        """
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
        """Find the day of the week a date falls on.

        Args:
            day: The date.

        Returns:
            Its day of the week.

        Examples:
            >>> from datetime import date
            >>> from alpha_led_sign import Weekday
            >>> Weekday.of(date(2026, 11, 15))
            <Weekday.SUNDAY: '1'>
        """
        return cls(str(day.isoweekday() % 7 + 1))


@dataclass(frozen=True)
class SetDayOfWeek(SpecialFunction):
    """Set the day of the week ("&", p. 22). The Sign advances it at midnight.

    Attributes:
        day: The day to set.
    """

    label: ClassVar[str] = "&"
    day: Weekday

    def encode_payload(self) -> bytes:
        """Encode the day as one digit, 1 for Sunday to 7 for Saturday.

        Returns:
            The Special Functions Data.
        """
        return self.day.value.encode("ascii")


class RunOrder(Enum):
    """How the Run Sequence picks the next TEXT File ("." K field, p. 23).

    Attributes:
        BY_RUN_TIME: Run each File during its Run Time. The default.
        IN_ORDER: Run every File in order, ignoring Run Times.
        DELETE_WHEN_DONE: Run each File during its Run Time, then delete it when its
            Stop Time passes.
    """

    BY_RUN_TIME = "T"
    IN_ORDER = "S"
    DELETE_WHEN_DONE = "D"


@dataclass(frozen=True, init=False)
class SetRunSequence(SpecialFunction):
    """Set the order the Sign shows TEXT Files in (".", p. 23).

    Args:
        labels: The File Labels of 1 to 128 TEXT Files, in order.
        order: How the Sign picks the next File.
        locked: Stop the Run Sequence from being changed with the IR keyboard.

    Attributes:
        labels: The File Labels, in order.
        order: How the Sign picks the next File.
        locked: Whether the IR keyboard can change the Run Sequence.

    Raises:
        ValueError: There are no labels or more than 128, or a File Label is
            invalid.
    """

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
        """Encode the run order, the lock byte, then the File Labels.

        Returns:
            The Special Functions Data.
        """
        order = self.order.value.encode("ascii")
        return order + lock_byte(self.locked) + "".join(self.labels).encode("ascii")


class RunDay(Enum):
    """The first day, or the set of days, a TEXT File runs ("2" S field, p. 24).

    Attributes:
        DAILY: Every day.
        SUNDAY: From Sunday to the stop day. The other single days work the same
            way.
        WEEKDAYS: Monday to Friday.
        WEEKENDS: Saturday and Sunday.
        ALWAYS: Always.
        NEVER: Never.
    """

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

    Attributes:
        start: The first day, or a set of days such as ``RunDay.WEEKDAYS``.
        stop: The last day. It matters only when ``start`` is a single day, but the
            Sign needs a value either way.

    Examples:
        >>> from alpha_led_sign import RunDay, RunDays, Weekday
        >>> RunDays(RunDay.MONDAY, Weekday.THURSDAY).encode()
        b'25'
    """

    start: RunDay
    stop: Weekday = Weekday.SUNDAY

    def encode(self) -> bytes:
        """Encode the start and stop days.

        Returns:
            Two characters: the start day's code, then the stop day's.
        """
        return (self.start.value + self.stop.value).encode("ascii")


@dataclass(frozen=True, init=False)
class SetRunDays(SpecialFunction):
    """Set which days TEXT Files run ("2", p. 24). Writing it ends a Priority TEXT File.

    Args:
        run_days: The Run Days for each File Label.

    Attributes:
        run_days: The File Labels and Run Days, in order.

    Raises:
        ValueError: A File Label is invalid.
    """

    label: ClassVar[str] = "2"
    run_days: tuple[tuple[str, RunDays], ...]

    def __init__(self, run_days: Mapping[str, RunDays]) -> None:
        for file_label in run_days:
            check_file_label(file_label)
        object.__setattr__(self, "run_days", tuple(run_days.items()))

    def encode_payload(self) -> bytes:
        """Encode each File Label followed by its Run Days.

        Returns:
            The Special Functions Data.
        """
        return b"".join(
            file_label.encode("ascii") + days.encode() for file_label, days in self.run_days
        )


@dataclass(frozen=True)
class SetSpeaker(SpecialFunction):
    """Turn the Sign's speaker on or off ("!", p. 21). It is off by default.

    Attributes:
        enabled: True to turn the speaker on.
    """

    label: ClassVar[str] = "!"
    enabled: bool

    def encode_payload(self) -> bytes:
        """Encode ``00`` to turn the speaker on, or ``FF`` to turn it off.

        Returns:
            The Special Functions Data.
        """
        return b"00" if self.enabled else b"FF"


FIXED_TONE_PAUSE = 3.0
"""Seconds to wait after a fixed tone before sending more (p. 27, note 4)."""


class Tone(Enum):
    """The Sign's built-in tones ("(", p. 22).

    Attributes:
        CONTINUOUS: A continuous tone for about 2 seconds.
        THREE_BEEPS: Three short beeps, about 2 seconds in all.
    """

    CONTINUOUS = "0"
    THREE_BEEPS = "1"


@dataclass(frozen=True)
class Beep(SpecialFunction):
    """Sound a built-in tone ("(", p. 22). It must be the last Command in a Packet.

    Attributes:
        tone: Which tone to play.
    """

    label: ClassVar[str] = "("
    must_be_last: ClassVar[bool] = True
    tone: Tone

    @property
    def pause_after(self) -> float:
        """Seconds to wait after a built-in tone: 3 (p. 27, note 4)."""
        return FIXED_TONE_PAUSE

    def encode_payload(self) -> bytes:
        """Encode the tone's one-character code.

        Returns:
            The Special Functions Data.
        """
        return self.tone.value.encode("ascii")


@dataclass(frozen=True)
class ProgrammableTone(SpecialFunction):
    """Sound a tone of a given pitch and length ("(" + "2", p. 22).

    It must be the last Command in a Packet.

    Attributes:
        frequency: The speaker setting, 0-254 (00H-FEH).
        duration: The length of one play, 1-15 tenths of a second.
        repeats: How many times to play it again, 0-15.

    Raises:
        ValueError: A value is out of range.
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
        """Seconds the tone plays, counting the first play and every repeat."""
        # p. 27 note 5: wait until the tone has finished. The manual doesn't say whether
        # "repeated" counts the first play, so assume it doesn't and wait the longer time.
        return self.duration * 0.1 * (self.repeats + 1)

    def encode_payload(self) -> bytes:
        """Encode ``2``, then the frequency, duration, and repeats in hex.

        Returns:
            The Special Functions Data.
        """
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
    """Set the Sign Address ("7", p. 26). A DIP switch address wins after a power cycle.

    Attributes:
        address: The new Sign Address, 0-255.

    Raises:
        ValueError: ``address`` is not 0-255.
    """

    label: ClassVar[str] = "7"
    address: int

    def __post_init__(self) -> None:
        check_sign_address(self.address)

    def encode_payload(self) -> bytes:
        """Encode the Sign Address as two hex digits.

        Returns:
            The Special Functions Data.
        """
        return f"{self.address:02X}".encode("ascii")


STRING_MAX_BYTES = 125
"""STRING File data is buffered, so it is limited to 125 bytes (p. 37)."""


@dataclass(frozen=True, init=False)
class WriteString(Command):
    """Write a STRING File (p. 37). Unlike a TEXT File write, the display does not blank.

    Args:
        label: The STRING File's File Label.
        content: Literal text, or a sequence of Segments.

    Attributes:
        label: The STRING File's File Label.
        content: The Segments, in order.

    Raises:
        ValueError: The File Label is invalid, the text is not printable ASCII, a
            Control Code can't go in a STRING File (Table 19), or the content
            encodes to more than 125 bytes.
    """

    code: ClassVar[str] = "G"
    label: str
    content: tuple[Segment, ...]

    def __init__(self, label: str, content: str | Sequence[Segment]) -> None:
        check_file_label(label)
        segments = normalize_content(content)
        for segment in segments:
            if not allowed_in_string_file(segment):
                raise ValueError(f"{segment!r} cannot be used in a STRING File (Table 19, p. 37)")
        object.__setattr__(self, "label", label)
        object.__setattr__(self, "content", segments)
        size = len(encode_content(segments))
        if size > STRING_MAX_BYTES:
            raise ValueError(f"STRING File data is at most {STRING_MAX_BYTES} bytes, got {size}")

    def encode_data(self) -> bytes:
        """Encode the File Label and the content.

        Returns:
            The Data Field.
        """
        return self.label.encode("ascii") + encode_content(self.content)

    def codes(self) -> Iterable[object]:
        """List the Control Codes in the content.

        Returns:
            The Control Codes, in order.
        """
        return (segment for segment in self.content if not isinstance(segment, str))


DOTS_PICTURE_ROWS_PAUSE = 0.1
"""Seconds of silence a SMALL DOTS PICTURE write needs after its Width (p. 40)."""


_RED_ONLY_PIXELS = frozenset({PixelColor.OFF, PixelColor.RED})


@dataclass(frozen=True)
class WriteDotsPicture(Command):
    """Write a SMALL DOTS PICTURE File (Table 22, p. 39). The display blanks until it ends.

    The picture's height and width must match the File's entry in the Memory
    Configuration (p. 39).

    Attributes:
        label: The DOTS PICTURE File's File Label.
        picture: The pixels.

    Raises:
        ValueError: The File Label is invalid.
    """

    code: ClassVar[str] = "I"
    label: str
    picture: DotsPicture

    def __post_init__(self) -> None:
        check_file_label(self.label)

    def encode_data(self) -> tuple[bytes | Pause, ...]:
        """Encode the File Label, Height, Width, and one row of pixel digits per CR.

        Returns:
            The Data Field in pieces, with the 100 ms Pause the Sign needs after the
            Width (p. 40).
        """
        size = f"{self.label}{self.picture.height:02X}{self.picture.width:02X}"
        rows = b"".join(
            "".join(pixel.value for pixel in row).encode("ascii") + b"\r"
            for row in self.picture.rows
        )
        # p. 40: at least 100 ms after the Width, before the Row Bit Patterns.
        return (size.encode("ascii"), Pause(DOTS_PICTURE_ROWS_PAUSE), rows)

    def requirements(self) -> Iterator[Requirement]:
        """List what the picture needs from a Sign Model.

        Yields:
            The base Requirements, then the Graphic Capability and a display at
            least as large as the picture (Table 70, note 1), then the Color
            Capability for each color other than off and red (Table 69, note 1).
        """
        yield from super().requirements()
        yield CapabilityRequirement(Capability.GRAPHIC, self)
        yield DisplaySizeRequirement(self.picture.width, self.picture.height, self)
        used = {pixel for row in self.picture.rows for pixel in row}
        for color in sorted(used - _RED_ONLY_PIXELS, key=lambda c: c.value):
            yield CapabilityRequirement(Capability.COLOR, color)


class Read[T](Command):
    """A Command that asks the Sign for data. It must be the last Command in a Packet.

    The Sign answers with a Response Command whose Command Code is ``response_code``
    and whose data starts with ``response_prefix``, so a Response can be matched to
    its Read without parsing it. ``Sign.query`` sends a Read and returns what
    ``parse`` makes of the answer.

    Attributes:
        response_code: The Command Code of the Response Command that answers this
            Read.
    """

    must_be_last: ClassVar[bool] = True

    response_code: ClassVar[str]

    @property
    def response_prefix(self) -> str:
        """What the answer's data starts with, such as a File Label."""
        return ""

    def answered_by(self, response: Sequence[ResponseItem]) -> bool:
        """Check whether a Response answers this Read.

        Args:
            response: A decoded Response.

        Returns:
            True if one of its Commands has ``response_code`` and starts with
            ``response_prefix``.
        """
        return any(self._is_answer(item) for item in response)

    def answer(self, response: Sequence[ResponseItem]) -> bytes:
        """Find this Read's answer in a Response.

        Args:
            response: A decoded Response.

        Returns:
            The answer's data, after ``response_prefix``.

        Raises:
            UnexpectedResponseError: The Response answers some other Read.
        """
        for item in response:
            if self._is_answer(item):
                return item.data[len(self.response_prefix) :]
        raise UnexpectedResponseError(
            f"the Response does not answer {type(self).__name__} "
            f"({self.response_code}{self.response_prefix}): {response!r}"
        )

    def _is_answer(self, item: ResponseItem) -> bool:
        prefix = self.response_prefix.encode("ascii")
        return item.code == self.response_code and item.data.startswith(prefix)

    @abstractmethod
    def parse(self, response: Sequence[ResponseItem]) -> T:
        """Turn a decoded Response into a value.

        Args:
            response: A decoded Response that answers this Read.

        Returns:
            The value the Read asked for.

        Raises:
            ResponseError: The answer's data is not in the expected format.
            UnexpectedResponseError: The Response answers some other Read.
        """


@dataclass(frozen=True)
class ReadText(Read[Message]):
    """Read a TEXT File back as a Message (p. 19). The Sign answers with a Write TEXT.

    Attributes:
        label: The TEXT File's File Label.

    Raises:
        ValueError: The File Label is invalid.
    """

    code: ClassVar[str] = "B"
    response_code: ClassVar[str] = "A"  # Table 46: answered with a Write TEXT
    label: str

    def __post_init__(self) -> None:
        check_file_label(self.label)

    def encode_data(self) -> bytes:
        """Encode the File Label to read.

        Returns:
            The Data Field.
        """
        return self.label.encode("ascii")

    @property
    def response_prefix(self) -> str:
        """The File Label: the answer's data starts with it."""
        return self.label

    def parse(self, response: Sequence[ResponseItem]) -> Message:
        """Decode the TEXT File data in the answer.

        Args:
            response: A decoded Response that answers this Read.

        Returns:
            The TEXT File's content.

        Raises:
            UnexpectedResponseError: The Response answers some other Read.
        """
        return decode_message(self.answer(response))


@dataclass(frozen=True)
class ReadString(Read[tuple[Segment, ...]]):
    """Read a STRING File's content (p. 38). The Sign answers with a Write STRING.

    Attributes:
        label: The STRING File's File Label.

    Raises:
        ValueError: The File Label is invalid.
    """

    code: ClassVar[str] = "H"
    response_code: ClassVar[str] = "G"  # Table 59: answered with a Write STRING
    label: str

    def __post_init__(self) -> None:
        check_file_label(self.label)

    def encode_data(self) -> bytes:
        """Encode the File Label to read.

        Returns:
            The Data Field.
        """
        return self.label.encode("ascii")

    @property
    def response_prefix(self) -> str:
        """The File Label: the answer's data starts with it."""
        return self.label

    def parse(self, response: Sequence[ResponseItem]) -> tuple[Segment, ...]:
        """Decode the STRING File data in the answer.

        Args:
            response: A decoded Response that answers this Read.

        Returns:
            The STRING File's text and Control Codes, in order.

        Raises:
            UnexpectedResponseError: The Response answers some other Read.
        """
        return decode_content(self.answer(response))


@dataclass(frozen=True)
class ReadDotsPicture(Read[DotsPicture]):
    """Read a SMALL DOTS PICTURE File (Table 23, p. 41). The Sign answers with an "I".

    Attributes:
        label: The DOTS PICTURE File's File Label.

    Raises:
        ValueError: The File Label is invalid.
    """

    code: ClassVar[str] = "J"
    response_code: ClassVar[str] = "I"  # p. 41: answered with an "I"
    label: str

    def __post_init__(self) -> None:
        check_file_label(self.label)

    def encode_data(self) -> bytes:
        """Encode the File Label to read.

        Returns:
            The Data Field.
        """
        return self.label.encode("ascii")

    @property
    def response_prefix(self) -> str:
        """The File Label: the answer's data starts with it."""
        return self.label

    def parse(self, response: Sequence[ResponseItem]) -> DotsPicture:
        """Decode the DOTS PICTURE File data in the answer.

        Args:
            response: A decoded Response that answers this Read.

        Returns:
            The picture, at the size the Sign reports.

        Raises:
            ResponseError: The data is not in the DOTS PICTURE format.
            UnexpectedResponseError: The Response answers some other Read.
        """
        return decode_dots_picture(self.answer(response))


class ReadSpecial[T](Read[T]):
    """A Read SPECIAL FUNCTION Command (Table 16, p. 29). The Sign answers with an "E".

    Attributes:
        label: The one-character Special Function label to read.
    """

    code: ClassVar[str] = "F"
    response_code: ClassVar[str] = "E"  # Table 53: answered with an "E"
    label: ClassVar[str]

    def encode_data(self) -> bytes:
        """Encode the Special Function label to read.

        Returns:
            The Data Field.
        """
        return self.label.encode("ascii")

    @property
    def response_prefix(self) -> str:
        """The Special Function label: the answer's data starts with it."""
        return self.label


@dataclass(frozen=True)
class ReadDayOfWeek(ReadSpecial[Weekday]):
    """Read the Sign's day of the week ("&", p. 30)."""

    label: ClassVar[str] = "&"

    def parse(self, response: Sequence[ResponseItem]) -> Weekday:
        """Decode the day of the week in the answer.

        Args:
            response: A decoded Response that answers this Read.

        Returns:
            The Sign's day of the week.

        Raises:
            UnexpectedResponseError: The Response answers some other Read.
        """
        return Weekday(self.answer(response).decode("ascii"))


@dataclass(frozen=True)
class SerialErrorStatus:
    """The Serial Error Status Register (p. 31): errors since it was last cleared.

    Attributes:
        illegal_command: The Sign got an illegal Command Code, File Label, or
            SPECIAL FUNCTION.
        checksum_error: A Command's Checksum did not match its data.
        buffer_overflow: The Sign's receive buffer overflowed.
        timeout: A serial timeout.
        framing_error: A framing error, usually a baud rate mismatch.
        parity_error: A parity error. Most Signs don't use it.
    """

    illegal_command: bool = False
    checksum_error: bool = False
    buffer_overflow: bool = False
    timeout: bool = False
    framing_error: bool = False
    parity_error: bool = False

    @classmethod
    def decode(cls, bits: int) -> "SerialErrorStatus":
        """Decode the register byte (p. 31).

        Args:
            bits: The byte. Bit 6 is always set; bits 5 to 0 are the errors.

        Returns:
            The decoded register.

        Examples:
            >>> from alpha_led_sign.protocol import SerialErrorStatus
            >>> SerialErrorStatus.decode(0x40).ok
            True
            >>> SerialErrorStatus.decode(0x50).checksum_error
            True
        """
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
        """Decode the register byte in the answer.

        Args:
            response: A decoded Response that answers this Read.

        Returns:
            The Sign's Serial Error Status Register.

        Raises:
            ResponseError: The answer is not one byte.
            UnexpectedResponseError: The Response answers some other Read.
        """
        data = self.answer(response)
        if len(data) != 1:
            raise ResponseError(f"expected one Serial Error Status byte, got {data!r}")
        return SerialErrorStatus.decode(data[0])


@dataclass(frozen=True)
class GeneralInformation:
    """What Read General Information reports (p. 29). Mostly useful for troubleshooting.

    Attributes:
        firmware: The firmware part number.
        revision: The firmware revision letter.
        firmware_date: The release month and two-digit year, as "MMYY".
        time: The Sign's time of day.
        time_format: Whether the Sign shows 12-hour or 24-hour time.
        speaker_enabled: Whether the speaker is on.
        memory_total: The size of the Memory Pool in bytes.
        memory_free: The unused part of the Memory Pool in bytes.
    """

    firmware: str
    revision: str
    firmware_date: str
    time: time
    time_format: TimeFormat
    speaker_enabled: bool
    memory_total: int
    memory_free: int


_GENERAL_INFORMATION_LENGTH = 29  # FFFFFFFF f MmYy HhNn R SS POOL,pool


@dataclass(frozen=True)
class ReadGeneralInformation(ReadSpecial[GeneralInformation]):
    """Read firmware, clock, speaker, and memory details ('"', p. 29)."""

    label: ClassVar[str] = '"'

    def parse(self, response: Sequence[ResponseItem]) -> GeneralInformation:
        """Decode the General Information in the answer.

        Args:
            response: A decoded Response that answers this Read.

        Returns:
            What the Sign reports about itself.

        Raises:
            ResponseError: The answer is not in the format p. 29 gives.
            UnexpectedResponseError: The Response answers some other Read.
        """
        data = self.answer(response)
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
    """One Sign's answer to a Network Query (p. 32).

    Attributes:
        sign_type: The Sign's Sign Type.
        address: The Sign's Sign Address.
        errors: The Sign's Serial Error Status Register.
    """

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
        """Decode one Sign's answer.

        Args:
            response: A decoded Response that answers this Read.

        Returns:
            The Sign's Sign Type, Sign Address, and serial errors.

        Raises:
            ResponseError: The answer is not 4 bytes, or its Sign Address is not hex.
            UnexpectedResponseError: The Response answers some other Read.
        """
        data = self.answer(response)
        if len(data) != 4:
            raise ResponseError(f"expected a 4-byte Network Query answer, got {data!r}")
        try:
            address = int(data[1:3].decode("ascii"), 16)
        except ValueError:
            raise ResponseError(f"bad Sign Address in Network Query answer {data!r}") from None
        return NetworkQueryResponse(chr(data[0]), address, SerialErrorStatus.decode(data[3]))
