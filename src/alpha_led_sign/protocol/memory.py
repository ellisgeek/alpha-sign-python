"""Files in a Memory Configuration, and the Run Times that schedule TEXT Files."""

from dataclasses import dataclass
from datetime import time
from enum import Enum
from typing import ClassVar

from alpha_led_sign.protocol.labels import check_file_label


@dataclass(frozen=True)
class RunTime:
    """When a TEXT File runs each day: Start and Stop Time codes (Appendix B, p. 51)."""

    start: int
    stop: int

    ALWAYS: ClassVar["RunTime"]
    NEVER: ClassVar["RunTime"]
    ALL_DAY: ClassVar["RunTime"]

    @classmethod
    def between(cls, start: time, stop: time) -> "RunTime":
        """Run from ``start`` until ``stop`` each day. Both must fall on a 10-minute step."""
        return cls(_time_code(start), _time_code(stop))

    def encode(self) -> bytes:
        return f"{self.start:02X}{self.stop:02X}".encode("ascii")


def _time_code(moment: time) -> int:
    """Appendix B: the number of 10-minute steps since midnight (8:50 a.m. = 35H)."""
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


def _lock(locked: bool) -> bytes:
    return b"L" if locked else b"U"


@dataclass(frozen=True)
class TextFile:
    """A TEXT File entry (type "A", p. 21).

    A size of 0 is allowed only for the last File, where it takes all remaining memory.
    """

    label: str
    size: int
    run_time: RunTime = RunTime.ALWAYS
    locked: bool = False
    """Locked Files cannot be changed from the IR keyboard."""

    def __post_init__(self) -> None:
        check_file_label(self.label)
        _check_size(self.size)

    def encode(self) -> bytes:
        head = f"{self.label}A".encode("ascii") + _lock(self.locked)
        return head + f"{self.size:04X}".encode("ascii") + self.run_time.encode()


@dataclass(frozen=True)
class StringFile:
    """A STRING File entry (type "B", p. 21). STRING Files are always locked."""

    label: str
    size: int

    def __post_init__(self) -> None:
        check_file_label(self.label)
        _check_size(self.size)

    def encode(self) -> bytes:
        return f"{self.label}BL{self.size:04X}0000".encode("ascii")


class PictureColors(Enum):
    """The color depth of a DOTS PICTURE File (p. 21)."""

    MONOCHROME = "1000"
    TRICOLOR = "2000"
    EIGHT_COLOR = "4000"


@dataclass(frozen=True)
class DotsPictureFile:
    """A DOTS PICTURE File entry (type "D", p. 21): space for a picture of this size."""

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
        head = f"{self.label}D".encode("ascii") + _lock(self.locked)
        size = f"{self.rows:02X}{self.columns:02X}{self.colors.value}"
        return head + size.encode("ascii")


type MemoryFile = TextFile | StringFile | DotsPictureFile
