"""Files in a Memory Configuration, and the Run Times that schedule TEXT Files."""

from dataclasses import dataclass
from datetime import time
from enum import Enum
from typing import ClassVar

from alpha_led_sign.protocol.labels import check_file_label


@dataclass(frozen=True)
class RunTime:
    """When a TEXT File runs each day: Start and Stop Time codes (Appendix B, p. 51).

    Build one with ``RunTime.between``, or use ``RunTime.ALWAYS``, ``RunTime.NEVER``,
    or ``RunTime.ALL_DAY``. With those three, the Stop Time is ignored.

    Attributes:
        start: The Start Time code: the number of 10-minute steps since midnight,
            or FDH-FFH for the three constants.
        stop: The Stop Time code.
        ALWAYS: Run whatever the time.
        NEVER: Never run.
        ALL_DAY: Run all day.
    """

    start: int
    stop: int

    ALWAYS: ClassVar["RunTime"]
    NEVER: ClassVar["RunTime"]
    ALL_DAY: ClassVar["RunTime"]

    @classmethod
    def between(cls, start: time, stop: time) -> "RunTime":
        """Run from one time until another each day.

        Args:
            start: The Start Time, on a 10-minute step.
            stop: The Stop Time, on a 10-minute step.

        Returns:
            The Run Time.

        Raises:
            ValueError: A time is not on a 10-minute step.

        Examples:
            >>> from datetime import time
            >>> from alpha_led_sign import RunTime
            >>> RunTime.between(time(8, 50), time(17, 0))
            RunTime(start=53, stop=102)
        """
        return cls(_time_code(start), _time_code(stop))

    def encode(self) -> bytes:
        """Encode the Start and Stop Time codes.

        Returns:
            Four hex digits.
        """
        return f"{self.start:02X}{self.stop:02X}".encode("ascii")


def _time_code(moment: time) -> int:
    """Convert a time to a Run Time code (Appendix B).

    Returns:
        The number of 10-minute steps since midnight: 8:50 a.m. is 35H.

    Raises:
        ValueError: The time is not on a 10-minute step.
    """
    if moment.minute % 10 or moment.second or moment.microsecond:
        raise ValueError(f"Run Times are in 10-minute steps, got {moment.isoformat()}")
    return moment.hour * 6 + moment.minute // 10


# The Stop Time is ignored for these; "00" matches Table 55.
RunTime.ALWAYS = RunTime(0xFF, 0x00)
RunTime.NEVER = RunTime(0xFE, 0x00)
RunTime.ALL_DAY = RunTime(0xFD, 0x00)


def _check_size(size: int) -> None:
    if not 0 <= size <= 0xFFFF:
        raise ValueError(f"a File size must be 0-65535 bytes (four hex digits), got {size}")


def lock_byte(locked: bool) -> bytes:
    """Encode the keyboard lock byte of a Memory Configuration entry or Run Sequence.

    Args:
        locked: True if the IR keyboard may not change it.

    Returns:
        ``L`` for locked, ``U`` for unlocked.
    """
    return b"L" if locked else b"U"


@dataclass(frozen=True)
class TextFile:
    """A TEXT File entry in a Memory Configuration (type "A", p. 21).

    Attributes:
        label: The File Label.
        size: The most bytes the File holds, 0-65535. A size of 0 is allowed only
            for the last File, where it takes the rest of memory.
        run_time: When the File runs each day.
        locked: True if the File can't be changed with the IR keyboard.

    Raises:
        ValueError: The File Label is invalid, or the size is out of range.
    """

    label: str
    size: int
    run_time: RunTime = RunTime.ALWAYS
    locked: bool = False

    def __post_init__(self) -> None:
        check_file_label(self.label)
        _check_size(self.size)

    def encode(self) -> bytes:
        """Encode the entry.

        Returns:
            The bytes of this entry in the Memory Configuration.
        """
        head = f"{self.label}A".encode("ascii") + lock_byte(self.locked)
        return head + f"{self.size:04X}".encode("ascii") + self.run_time.encode()


@dataclass(frozen=True)
class StringFile:
    """A STRING File entry in a Memory Configuration (type "B", p. 21).

    STRING Files are always locked: the IR keyboard can't change them.

    Attributes:
        label: The File Label.
        size: The most bytes the File holds, 1-65535. A write holds at most 125.

    Raises:
        ValueError: The File Label is invalid, or the size is out of range.
    """

    label: str
    size: int

    def __post_init__(self) -> None:
        check_file_label(self.label)
        _check_size(self.size)
        if self.size == 0:
            # p. 27, note 1: only a last TEXT File may have size 0.
            raise ValueError("a STRING File cannot have size 0")

    def encode(self) -> bytes:
        """Encode the entry.

        Returns:
            The bytes of this entry in the Memory Configuration.
        """
        return f"{self.label}BL{self.size:04X}0000".encode("ascii")


class PictureColors(Enum):
    """The color depth of a DOTS PICTURE File (p. 21).

    Attributes:
        MONOCHROME: One color.
        TRICOLOR: Red, green, and amber.
        EIGHT_COLOR: Eight colors.
    """

    MONOCHROME = "1000"
    TRICOLOR = "2000"
    EIGHT_COLOR = "4000"


@dataclass(frozen=True)
class DotsPictureFile:
    """A DOTS PICTURE File entry in a Memory Configuration (type "D", p. 21).

    It makes room for a picture of this size. The picture written to it must be the
    same size.

    Attributes:
        label: The File Label.
        rows: The picture's height in pixels, 0-255.
        columns: The picture's width in pixels, 0-255.
        colors: The color depth.
        locked: True if the File can't be changed with the IR keyboard.

    Raises:
        ValueError: The File Label is invalid, or a size is out of range.
    """

    label: str
    rows: int
    columns: int
    colors: PictureColors = PictureColors.MONOCHROME
    locked: bool = False

    def __post_init__(self) -> None:
        check_file_label(self.label)
        if not (0 <= self.rows <= 0xFF and 0 <= self.columns <= 0xFF):
            raise ValueError("DOTS PICTURE rows and columns must each be 0-255")

    def encode(self) -> bytes:
        """Encode the entry.

        Returns:
            The bytes of this entry in the Memory Configuration.
        """
        head = f"{self.label}D".encode("ascii") + lock_byte(self.locked)
        size = f"{self.rows:02X}{self.columns:02X}{self.colors.value}"
        return head + size.encode("ascii")


type MemoryFile = TextFile | StringFile | DotsPictureFile
"""One entry in a Memory Configuration."""
