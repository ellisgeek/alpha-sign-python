"""Codes used inside TEXT Files: Modes, Display Positions, and Control Codes."""

from dataclasses import dataclass
from enum import Enum
from typing import Protocol, runtime_checkable

from alpha_led_sign.protocol.labels import check_file_label


@runtime_checkable
class ControlCode(Protocol):
    """Anything that can sit in a Frame's content and encode to Control Code bytes.

    Every Control Code type in this module meets it. Content may hold any object
    with an ``encode`` method, but validation and markup know only the types the
    library defines.
    """

    def encode(self) -> bytes:
        """Encode this Control Code.

        Returns:
            The bytes that stand for it in a TEXT or STRING File.
        """
        ...


class Position(Enum):
    """Display Position: the lines of a multi-line Sign a Frame uses (Table 12, p. 18).

    On a one-line Sign every position shows on the one line.

    Attributes:
        MIDDLE: Centered on the display. On a two-line Sign it is the only position
            that shows a font taller than 7 rows at full height.
        TOP: The top line.
        BOTTOM: The bottom line.
        FILL: Every line, filled with the text. The default.
        LEFT: The left part of the display. Alpha 3.0 only.
        RIGHT: The right part of the display. Alpha 3.0 only.
    """

    MIDDLE = " "
    TOP = '"'
    BOTTOM = "&"
    FILL = "0"
    LEFT = "1"
    RIGHT = "2"


class Mode(Enum):
    """The standard Modes: how a Frame comes onto the display (Table 65, p. 89).

    ``EXPLODE`` and ``CLOCK`` need Alpha 3.0. The Special Modes and Special Graphics
    have their own enums, ``SpecialMode`` and ``SpecialGraphic``. In markup a Mode is
    ``{frame NAME}``, such as ``{frame rotate}``.
    """

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
        """The Mode Code as it appears in a Mode Field, after the Display Position."""
        return self.value


SPECIAL = "n"
"""The Mode Code that introduces a Special Specifier (Table 65)."""


class SpecialMode(Enum):
    """Special Modes, sent as Mode Code "n" plus a Special Specifier (Table 66, p. 89).

    In markup a Special Mode is ``{frame special NAME}``, such as
    ``{frame special snow}``. The manual lists ``WELCOME`` and ``SLOT_MACHINE`` as
    animations, and ``NEWS_FLASH`` and ``TRUMPET`` are for the BetaBrite model 1036.
    """

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
        """The Mode Code ``n`` and Special Specifier, as they appear in a Mode Field."""
        return SPECIAL + self.value


class SpecialGraphic(Enum):
    """Special Graphics: built-in animations, sent as Mode Code "n" plus a Special Specifier.

    Table 67, p. 90. A Frame with a Special Graphic can't also show text, so put the
    text in the next Frame. In markup a Special Graphic is ``{frame graphic NAME}``,
    such as ``{frame graphic fireworks}``.
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
        """The Mode Code ``n`` and Special Specifier, as they appear in a Mode Field."""
        return SPECIAL + self.value


class Font(Enum):
    """Character sets, selected with 1AH (Appendix G, p. 82).

    The name gives the height in rows. ``FULL_HEIGHT`` and ``FULL_HEIGHT_FANCY`` are
    15 or 16 rows high, and ``TEN_HIGH`` is 10. On a two-line Sign only
    ``Position.MIDDLE`` shows those three at full height. The stroke, shadow, and
    wide fonts are for the BetaBrite model 1036. In markup a font is ``{font NAME}``,
    such as ``{font seven_high}``.
    """

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
        """Encode this Control Code.

        Returns:
            The bytes that stand for it in a TEXT or STRING File.
        """
        return b"\x1a" + self.value.encode("ascii")


class Color(Enum):
    """Character colors, selected with 1CH (Appendix G, p. 82).

    A red-only model (an "R" model) has none of them. In markup a color is
    ``{color NAME}``, such as ``{color amber}``. A STRING File can't hold
    ``RAINBOW_1`` or ``RAINBOW_2`` (Table 19).
    """

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
        """Encode this Control Code.

        Returns:
            The bytes that stand for it in a TEXT or STRING File.
        """
        return b"\x1c" + self.value.encode("ascii")


class Speed(Enum):
    """How fast the following text is shown (Appendix G, p. 81).

    In markup a speed is ``{speed 1}`` to ``{speed 5}``, or ``{speed no_hold}``.

    Attributes:
        SPEED_1: The slowest.
        SPEED_2: The second slowest.
        SPEED_3: The middle speed.
        SPEED_4: The second fastest.
        SPEED_5: The fastest.
        NO_HOLD: Almost no pause after the Mode. It has no effect with ROTATE or
            COMPRESSED_ROTATE.
    """

    SPEED_1 = b"\x15"
    SPEED_2 = b"\x16"
    SPEED_3 = b"\x17"
    SPEED_4 = b"\x18"
    SPEED_5 = b"\x19"
    NO_HOLD = b"\x09"

    def encode(self) -> bytes:
        """Encode this Control Code.

        Returns:
            The bytes that stand for it in a TEXT or STRING File.
        """
        return self.value


class Control(Enum):
    """Single-byte layout Control Codes (Appendix G, p. 81).

    Literal text can't hold a newline; use ``Control.NEW_LINE`` (``{new_line}``).
    A STRING File may hold ``NEW_LINE`` but not ``NEW_PAGE``.

    Attributes:
        NEW_LINE: Start a new line.
        NEW_PAGE: Start a new page.
    """

    NEW_LINE = b"\x0d"
    NEW_PAGE = b"\x0c"

    def encode(self) -> bytes:
        """Encode this Control Code.

        Returns:
            The bytes that stand for it in a TEXT or STRING File.
        """
        return self.value


class Spacing(Enum):
    """Character spacing, selected with 1EH (Appendix G, p. 82).

    Attributes:
        PROPORTIONAL: Each character takes its own width.
        FIXED_WIDTH: Every character takes the same width.
    """

    PROPORTIONAL = "0"
    FIXED_WIDTH = "1"

    def encode(self) -> bytes:
        """Encode this Control Code.

        Returns:
            The bytes that stand for it in a TEXT or STRING File.
        """
        return b"\x1e" + self.value.encode("ascii")


def _switch(on: bool) -> bytes:
    return b"1" if on else b"0"


@dataclass(frozen=True)
class Wide:
    """Wide characters on (12H) or off (11H) (Appendix G, p. 81).

    In markup it is ``{wide on}`` or ``{wide off}``.

    Attributes:
        on: True to turn it on, False to turn it off.
    """

    on: bool = True

    def encode(self) -> bytes:
        """Encode this Control Code.

        Returns:
            The bytes that stand for it in a TEXT or STRING File.
        """
        return b"\x12" if self.on else b"\x11"


@dataclass(frozen=True)
class DoubleHigh:
    """Double-height characters on or off, with 05H (Appendix G, p. 81).

    In markup it is ``{double_high on}`` or ``{double_high off}``.

    Attributes:
        on: True to turn it on, False to turn it off.
    """

    on: bool = True

    def encode(self) -> bytes:
        """Encode this Control Code.

        Returns:
            The bytes that stand for it in a TEXT or STRING File.
        """
        return b"\x05" + _switch(self.on)


@dataclass(frozen=True)
class TrueDescenders:
    """True descenders on or off, with 06H (Appendix G, p. 81).

    In markup it is ``{descenders on}`` or ``{descenders off}``.

    Attributes:
        on: True to turn it on, False to turn it off.
    """

    on: bool = True

    def encode(self) -> bytes:
        """Encode this Control Code.

        Returns:
            The bytes that stand for it in a TEXT or STRING File.
        """
        return b"\x06" + _switch(self.on)


@dataclass(frozen=True)
class CharacterFlash:
    """Flashing characters on or off, with 07H (Appendix G, p. 81).

    In markup it is ``{flash on}`` or ``{flash off}``.

    Attributes:
        on: True to turn it on, False to turn it off.
    """

    on: bool = True

    def encode(self) -> bytes:
        """Encode this Control Code.

        Returns:
            The bytes that stand for it in a TEXT or STRING File.
        """
        return b"\x07" + _switch(self.on)


class Attribute(Enum):
    """Character attributes set with 1DH (Appendix G, p. 82). All are off by default.

    ``CharacterAttribute`` turns one on or off.

    Attributes:
        WIDE: Wide characters.
        DOUBLE_WIDE: Double-wide characters.
        DOUBLE_HIGH: Double-height characters.
        TRUE_DESCENDERS: True descenders.
        FIXED_WIDTH: Fixed-width characters.
        FANCY: The fancy form of the font.
        AUXILIARY_PORT: The auxiliary port. 4000 and 7000 Series only.
        SHADOW: Shadow characters. BetaBrite model 1036 and AlphaPremiere 9000
            only.
    """

    WIDE = "0"
    DOUBLE_WIDE = "1"
    DOUBLE_HIGH = "2"
    TRUE_DESCENDERS = "3"
    FIXED_WIDTH = "4"
    FANCY = "5"
    AUXILIARY_PORT = "6"
    SHADOW = "7"


@dataclass(frozen=True)
class CharacterAttribute:
    """Turn one character Attribute on or off (3-byte format, Appendix G, p. 82).

    In markup it is ``{attribute NAME on}`` or ``{attribute NAME off}``, such as
    ``{attribute fancy on}``.

    Attributes:
        attribute: The Attribute to change.
        on: True to turn it on, False to turn it off.
    """

    attribute: Attribute
    on: bool = True

    def encode(self) -> bytes:
        """Encode this Control Code.

        Returns:
            The bytes that stand for it in a TEXT or STRING File.
        """
        return b"\x1d" + self.attribute.value.encode("ascii") + _switch(self.on)


@dataclass(frozen=True)
class CurrentTime:
    """Show the Sign's time of day (13H, Appendix G, p. 81).

    The Sign shows its own clock, set with ``Sign.set_clock``, in the format set with
    ``Sign.set_time_format``. In markup it is ``{time}``.
    """

    def encode(self) -> bytes:
        """Encode this Control Code.

        Returns:
            The bytes that stand for it in a TEXT or STRING File.
        """
        return b"\x13"


class DateFormat(Enum):
    """Date formats for CurrentDate (0BH, Appendix G, p. 81).

    In markup a format is the member name in lowercase, such as
    ``{date mmm_dd_yyyy}``.

    Attributes:
        MM_DD_YY_SLASH: Month first, with slashes. The default.
        DD_MM_YY_SLASH: Day first, with slashes.
        MM_DD_YY_DASH: Month first, with dashes.
        DD_MM_YY_DASH: Day first, with dashes.
        MM_DD_YY_DOT: Month first, with dots.
        DD_MM_YY_DOT: Day first, with dots.
        MM_DD_YY_SPACE: Month first, with spaces.
        DD_MM_YY_SPACE: Day first, with spaces.
        MMM_DD_YYYY: The month's short name, for example "NOV.07, 2026".
        DAY_OF_WEEK: The day of the week.
    """

    MM_DD_YY_SLASH = "0"
    DD_MM_YY_SLASH = "1"
    MM_DD_YY_DASH = "2"
    DD_MM_YY_DASH = "3"
    MM_DD_YY_DOT = "4"
    DD_MM_YY_DOT = "5"
    MM_DD_YY_SPACE = "6"
    DD_MM_YY_SPACE = "7"
    MMM_DD_YYYY = "8"
    DAY_OF_WEEK = "9"


@dataclass(frozen=True)
class CurrentDate:
    """Show the Sign's date (0BH, Appendix G, p. 81).

    In markup it is ``{date}`` or ``{date FORMAT}``.

    Attributes:
        format: How the date is written.
    """

    format: DateFormat = DateFormat.MM_DD_YY_SLASH

    def encode(self) -> bytes:
        """Encode this Control Code.

        Returns:
            The bytes that stand for it in a TEXT or STRING File.
        """
        return b"\x0b" + self.format.value.encode("ascii")


@dataclass(frozen=True)
class StringRef:
    """Show the current contents of a STRING File (10H + File Label, Appendix G, p. 81).

    Writing the STRING File with ``Sign.write_string`` changes what the TEXT File
    shows, without blanking the display. In markup it is ``{string LABEL}``.

    Attributes:
        label: The STRING File's File Label.

    Raises:
        ValueError: ``label`` is not one character from 20H to 7EH.
    """

    label: str

    def __post_init__(self) -> None:
        check_file_label(self.label)

    def encode(self) -> bytes:
        """Encode this Control Code.

        Returns:
            The bytes that stand for it in a TEXT or STRING File.
        """
        return b"\x10" + self.label.encode("ascii")


@dataclass(frozen=True)
class DotsPictureRef:
    """Show a SMALL DOTS PICTURE File (14H + File Label, Appendix G, p. 81).

    In markup it is ``{picture LABEL}``. A STRING File can't hold it (Table 19).

    Attributes:
        label: The DOTS PICTURE File's File Label.

    Raises:
        ValueError: ``label`` is not one character from 20H to 7EH.
    """

    label: str

    def __post_init__(self) -> None:
        check_file_label(self.label)

    def encode(self) -> bytes:
        """Encode this Control Code.

        Returns:
            The bytes that stand for it in a TEXT or STRING File.
        """
        return b"\x14" + self.label.encode("ascii")


@dataclass(frozen=True)
class RawControl:
    """Control Code bytes the library does not model.

    A read returns one for each Control Code it can't decode, so that the content
    can be written back unchanged. In markup it is ``{raw HEX}``, such as
    ``{raw 1F41}``.

    Attributes:
        data: The bytes, sent as they are.
    """

    data: bytes

    def encode(self) -> bytes:
        """Encode this Control Code.

        Returns:
            The bytes that stand for it in a TEXT or STRING File.
        """
        return self.data
