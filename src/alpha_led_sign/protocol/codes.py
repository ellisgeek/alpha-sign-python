"""Codes used inside TEXT Files: Modes, Display Positions, and Control Codes."""

from dataclasses import dataclass
from enum import Enum
from typing import Protocol, runtime_checkable

from alpha_led_sign.protocol.labels import check_file_label


@runtime_checkable
class ControlCode(Protocol):
    """Anything that can sit in a Frame's content and encode to Control Code bytes."""

    def encode(self) -> bytes: ...


class Position(Enum):
    """Display Position: the lines of a multi-line Sign a Frame uses (Table 12, p. 18)."""

    MIDDLE = " "
    TOP = '"'
    BOTTOM = "&"
    FILL = "0"
    LEFT = "1"
    """Alpha 3.0 only."""
    RIGHT = "2"
    """Alpha 3.0 only."""


class Mode(Enum):
    """Standard Modes (Table 65, p. 89). SPECIAL ("n") is expressed by SpecialMode."""

    ROTATE = "a"
    HOLD = "b"
    FLASH = "c"
    ROLL_UP = "e"
    ROLL_DOWN = "f"
    ROLL_LEFT = "g"
    ROLL_RIGHT = "h"
    WIPE_UP = "i"
    WIPE_DOWN = "j"
    WIPE_LEFT = "k"
    WIPE_RIGHT = "l"
    SCROLL = "m"
    AUTOMODE = "o"
    ROLL_IN = "p"
    ROLL_OUT = "q"
    WIPE_IN = "r"
    WIPE_OUT = "s"
    COMPRESSED_ROTATE = "t"
    EXPLODE = "u"
    CLOCK = "v"

    @property
    def field(self) -> str:
        """The Mode Code as it appears in a Mode Field."""
        return self.value


SPECIAL = "n"
"""The Mode Code that introduces a Special Specifier (Table 65)."""


class SpecialMode(Enum):
    """Special Modes, sent as Mode Code "n" plus a Special Specifier (Table 66, p. 89)."""

    TWINKLE = "0"
    SPARKLE = "1"
    SNOW = "2"
    INTERLOCK = "3"
    SWITCH = "4"
    SLIDE = "5"
    SPRAY = "6"
    STARBURST = "7"
    WELCOME = "8"
    SLOT_MACHINE = "9"
    # Table 66 gives "A"/"B" with hex 3AH/3BH. The letters agree with CYCLE_COLORS
    # ("C" = 43H) beside them, so the hex is taken to be the error.
    NEWS_FLASH = "A"
    TRUMPET = "B"
    CYCLE_COLORS = "C"

    @property
    def field(self) -> str:
        return SPECIAL + self.value


class SpecialGraphic(Enum):
    """Special Graphics: built-in animations, sent as Mode Code "n" plus a Special Specifier.

    Table 67, p. 90. A Frame with a Special Graphic cannot also show text.
    """

    THANK_YOU = "S"
    NO_SMOKING = "U"
    DONT_DRINK_AND_DRIVE = "V"
    RUNNING_ANIMAL = "W"
    FIREWORKS = "X"
    TURBO_CAR = "Y"
    CHERRY_BOMB = "Z"

    @property
    def field(self) -> str:
        return SPECIAL + self.value


class Font(Enum):
    """Character sets, selected with 1AH (Appendix G, p. 82)."""

    FIVE_HIGH = "1"
    FIVE_STROKE = "2"
    SEVEN_HIGH = "3"
    SEVEN_STROKE = "4"
    SEVEN_HIGH_FANCY = "5"
    TEN_HIGH = "6"
    SEVEN_SHADOW = "7"
    FULL_HEIGHT_FANCY = "8"
    FULL_HEIGHT = "9"
    SEVEN_SHADOW_FANCY = ":"
    FIVE_WIDE = ";"
    SEVEN_WIDE = "<"
    SEVEN_FANCY_WIDE = "="
    WIDE_STROKE_FIVE = ">"

    def encode(self) -> bytes:
        return b"\x1a" + self.value.encode("ascii")


class Color(Enum):
    """Character colors, selected with 1CH (Appendix G, p. 82). Not every Sign has all."""

    RED = "1"
    GREEN = "2"
    AMBER = "3"
    DIM_RED = "4"
    DIM_GREEN = "5"
    BROWN = "6"
    ORANGE = "7"
    YELLOW = "8"
    RAINBOW_1 = "9"
    RAINBOW_2 = "A"
    COLOR_MIX = "B"
    AUTOCOLOR = "C"

    def encode(self) -> bytes:
        return b"\x1c" + self.value.encode("ascii")


class Speed(Enum):
    """Display speed for the following text (Appendix G, p. 81)."""

    SPEED_1 = b"\x15"
    """Slowest."""
    SPEED_2 = b"\x16"
    SPEED_3 = b"\x17"
    SPEED_4 = b"\x18"
    SPEED_5 = b"\x19"
    """Fastest."""
    NO_HOLD = b"\x09"
    """Virtually no pause after the Mode. Has no effect with ROTATE or COMPRESSED_ROTATE."""

    def encode(self) -> bytes:
        return self.value


class Control(Enum):
    """Single-byte layout Control Codes (Appendix G, p. 81)."""

    NEW_LINE = b"\x0d"
    NEW_PAGE = b"\x0c"

    def encode(self) -> bytes:
        return self.value


class Spacing(Enum):
    """Character spacing, selected with 1EH (Appendix G, p. 82)."""

    PROPORTIONAL = "0"
    FIXED_WIDTH = "1"

    def encode(self) -> bytes:
        return b"\x1e" + self.value.encode("ascii")


def _switch(on: bool) -> bytes:
    return b"1" if on else b"0"


@dataclass(frozen=True)
class Wide:
    """Wide characters on (12H) or off (11H) (Appendix G, p. 81)."""

    on: bool = True

    def encode(self) -> bytes:
        return b"\x12" if self.on else b"\x11"


@dataclass(frozen=True)
class DoubleHigh:
    """Double-height characters on or off, with 05H (Appendix G, p. 81)."""

    on: bool = True

    def encode(self) -> bytes:
        return b"\x05" + _switch(self.on)


@dataclass(frozen=True)
class TrueDescenders:
    """True descenders on or off, with 06H (Appendix G, p. 81)."""

    on: bool = True

    def encode(self) -> bytes:
        return b"\x06" + _switch(self.on)


@dataclass(frozen=True)
class CharacterFlash:
    """Flashing characters on or off, with 07H (Appendix G, p. 81)."""

    on: bool = True

    def encode(self) -> bytes:
        return b"\x07" + _switch(self.on)


class Attribute(Enum):
    """Character attributes set with 1DH (Appendix G, p. 82). All are off by default."""

    WIDE = "0"
    DOUBLE_WIDE = "1"
    DOUBLE_HIGH = "2"
    TRUE_DESCENDERS = "3"
    FIXED_WIDTH = "4"
    FANCY = "5"
    AUXILIARY_PORT = "6"
    """4000 and 7000 Series only."""
    SHADOW = "7"
    """BetaBrite model 1036 and AlphaPremiere 9000 only."""


@dataclass(frozen=True)
class CharacterAttribute:
    """Turn one character Attribute on or off (3-byte format, Appendix G, p. 82)."""

    attribute: Attribute
    on: bool = True

    def encode(self) -> bytes:
        return b"\x1d" + self.attribute.value.encode("ascii") + _switch(self.on)


@dataclass(frozen=True)
class CurrentTime:
    """Show the Sign's time of day (13H, Appendix G, p. 81)."""

    def encode(self) -> bytes:
        return b"\x13"


class DateFormat(Enum):
    """Date formats for CurrentDate (0BH, Appendix G, p. 81)."""

    MM_DD_YY_SLASH = "0"
    DD_MM_YY_SLASH = "1"
    MM_DD_YY_DASH = "2"
    DD_MM_YY_DASH = "3"
    MM_DD_YY_DOT = "4"
    DD_MM_YY_DOT = "5"
    MM_DD_YY_SPACE = "6"
    DD_MM_YY_SPACE = "7"
    MMM_DD_YYYY = "8"
    """For example "NOV.07, 2026"."""
    DAY_OF_WEEK = "9"


@dataclass(frozen=True)
class CurrentDate:
    """Show the Sign's date in the given format (0BH, Appendix G, p. 81)."""

    format: DateFormat = DateFormat.MM_DD_YY_SLASH

    def encode(self) -> bytes:
        return b"\x0b" + self.format.value.encode("ascii")


@dataclass(frozen=True)
class StringRef:
    """Insert the current contents of a STRING File (10H + File Label, Appendix G, p. 81)."""

    label: str

    def __post_init__(self) -> None:
        check_file_label(self.label)

    def encode(self) -> bytes:
        return b"\x10" + self.label.encode("ascii")


@dataclass(frozen=True)
class DotsPictureRef:
    """Show a SMALL DOTS PICTURE File (14H + File Label, Appendix G, p. 81)."""

    label: str

    def __post_init__(self) -> None:
        check_file_label(self.label)

    def encode(self) -> bytes:
        return b"\x14" + self.label.encode("ascii")


@dataclass(frozen=True)
class RawControl:
    """Control Code bytes the library does not model, kept so they can be sent back as-is."""

    data: bytes

    def encode(self) -> bytes:
        return self.data


def _switch_from(byte: int) -> bool:
    if byte not in b"01":
        raise ValueError(f"expected '0' or '1', got {byte!r}")
    return byte == ord("1")


_SINGLE: dict[int, ControlCode] = {
    0x0C: Control.NEW_PAGE,
    0x0D: Control.NEW_LINE,
    0x11: Wide(False),
    0x12: Wide(True),
    0x13: CurrentTime(),
    **{speed.value[0]: speed for speed in Speed},
}

_PAIRED = {
    0x05: lambda byte: DoubleHigh(_switch_from(byte)),
    0x06: lambda byte: TrueDescenders(_switch_from(byte)),
    0x07: lambda byte: CharacterFlash(_switch_from(byte)),
    0x0B: lambda byte: CurrentDate(DateFormat(chr(byte))),
    0x10: lambda byte: StringRef(chr(byte)),
    0x14: lambda byte: DotsPictureRef(chr(byte)),
    0x1A: lambda byte: Font(chr(byte)),
    0x1C: lambda byte: Color(chr(byte)),
    0x1E: lambda byte: Spacing(chr(byte)),
}

# Codes the library keeps as RawControl, with their total length (Appendix G).
_RAW_LENGTHS = {
    0x08: 2,  # extended character, temperature, or counter
    0x1F: 15,  # call picture or animation File
}


def decode_control(data: bytes, start: int) -> tuple[ControlCode, int]:
    """Decode the Control Code at ``data[start]``; return it and the index after it."""
    first = data[start]
    if first in _SINGLE:
        return _SINGLE[first], start + 1
    try:
        if first in _PAIRED and start + 1 < len(data):
            return _PAIRED[first](data[start + 1]), start + 2
        if first == 0x1D and start + 2 < len(data):
            attribute = Attribute(chr(data[start + 1]))
            return CharacterAttribute(attribute, _switch_from(data[start + 2])), start + 3
    except ValueError:
        pass  # a parameter the library doesn't know, such as an Alpha 3.0 RGB color
    if first == 0x1C and data[start + 1 : start + 2] in (b"Y", b"Z"):
        end = start + 8  # 1CH + "Y" or "Z" + RRGGBB (Alpha 3.0)
    elif first in _PAIRED or first == 0x1D:
        end = start + (3 if first == 0x1D else 2)
    else:
        end = start + _RAW_LENGTHS.get(first, 1)
    return RawControl(data[start:end]), min(end, len(data))
