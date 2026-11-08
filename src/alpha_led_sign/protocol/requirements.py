"""What each Mode, Display Position, and Control Code needs from a Sign Model.

The Capabilities are the columns of Tables 68-70; the Protocol Versions come from
the tables that list each code.
"""

from enum import Enum
from typing import NamedTuple

from alpha_led_sign.protocol.codes import (
    Attribute,
    CharacterAttribute,
    CharacterFlash,
    Color,
    Control,
    CurrentDate,
    CurrentTime,
    DoubleHigh,
    Font,
    Mode,
    Position,
    Spacing,
    SpecialGraphic,
    SpecialMode,
    Speed,
    StringRef,
    TrueDescenders,
    Wide,
)
from alpha_led_sign.protocol.versions import ProtocolVersion


class Capability(Enum):
    """One feature a Sign Model can or cannot use, one per column of Tables 68-70."""

    # Table 68: Modes.
    AUTOMODE = "automode"
    FLASH = "flash"
    HOLD = "hold"
    INTERLOCK = "interlock"
    ROLL = "roll up/down/left/right"
    ROLL_IN_OUT = "roll in/out"
    ROTATE = "rotate"
    COMPRESSED_ROTATE = "compressed rotate"
    SCROLL = "scroll"
    SLIDE = "slide"
    CYCLE_COLORS = "cycle colors"
    SNOW = "snow"
    SPARKLE = "sparkle"
    SPRAY = "spray"
    STARBURST = "starburst"
    SWITCH = "switch"
    TWINKLE = "twinkle"
    WIPE = "wipe up/down/left/right"
    WIPE_IN_OUT = "wipe in/out"
    EXPLODE = "explode"
    CLOCK = "clock"
    LEFT_RIGHT_POSITION = "left/right display position"
    # Table 69: fonts and colors.
    FONT_FULL_HEIGHT = "15/16-row font"
    FONT_FULL_HEIGHT_FANCY = "15/16-row fancy font"
    FONT_TEN_HIGH = "10-row font"
    FONT_SEVEN_HIGH = "7-row font"
    FONT_SEVEN_HIGH_FANCY = "7-row fancy font"
    FONT_FIVE_HIGH = "5-row font"
    COLOR = "color"
    WIDE = "wide characters"
    DOUBLE_WIDE = "double-wide characters"
    CHARACTER_FLASH = "flashing characters"
    DOUBLE_HIGH = "double-height characters"
    TRUE_DESCENDERS = "true descenders"
    FIXED_WIDTH = "fixed-width characters"
    # Table 70: display options.
    TIME = "time"
    DATE = "date"
    TEMPERATURE_FAHRENHEIT = "temperature in Fahrenheit"
    TEMPERATURE_CELSIUS = "temperature in Celsius"
    SPEED = "speed"
    NEW_LINE = "new line"
    NEW_PAGE = "new page"
    ANIMATION = "animation"
    STRING = "STRING File"
    TICKER_SYMBOL = "ticker symbol"
    VARIABLE = "variable"
    COUNTER = "counter"
    GRAPHIC = "graphic"
    GIF = "GIF"
    FLICK = "flick"
    MESSAGE = "message"
    # Not in the tables: Appendix G footnotes limit these to the BetaBrite model 1036.
    BETABRITE_1036_FONTS = "BetaBrite 1036 fonts"
    BETABRITE_1036_ANIMATIONS = "BetaBrite 1036 animations"


class Requirement(NamedTuple):
    """What a code needs from a Sign Model."""

    version: ProtocolVersion
    """The earliest Protocol Version that has the code."""
    capability: Capability | None
    """The Capability it needs, or None when it needs none (such as a top-line Position)."""


def requires(code: object) -> Requirement:
    """What ``code`` (a Mode, Display Position, or Control Code) needs from a Sign Model.

    Codes the manual does not mark with a version work with every version.
    """
    return Requirement(_MIN_VERSIONS.get(code, ProtocolVersion.EZ_KEY_II), _capability(code))


_MIN_VERSIONS: dict[object, ProtocolVersion] = {
    Position.LEFT: ProtocolVersion.ALPHA_3_0,  # Table 12
    Position.RIGHT: ProtocolVersion.ALPHA_3_0,  # Table 12
    Mode.EXPLODE: ProtocolVersion.ALPHA_3_0,  # Table 65
    Mode.CLOCK: ProtocolVersion.ALPHA_3_0,  # Table 65
}


_MODES = {
    Mode.ROTATE: Capability.ROTATE,
    Mode.HOLD: Capability.HOLD,
    Mode.FLASH: Capability.FLASH,
    Mode.ROLL_UP: Capability.ROLL,
    Mode.ROLL_DOWN: Capability.ROLL,
    Mode.ROLL_LEFT: Capability.ROLL,
    Mode.ROLL_RIGHT: Capability.ROLL,
    Mode.WIPE_UP: Capability.WIPE,
    Mode.WIPE_DOWN: Capability.WIPE,
    Mode.WIPE_LEFT: Capability.WIPE,
    Mode.WIPE_RIGHT: Capability.WIPE,
    Mode.SCROLL: Capability.SCROLL,
    Mode.AUTOMODE: Capability.AUTOMODE,
    Mode.ROLL_IN: Capability.ROLL_IN_OUT,
    Mode.ROLL_OUT: Capability.ROLL_IN_OUT,
    Mode.WIPE_IN: Capability.WIPE_IN_OUT,
    Mode.WIPE_OUT: Capability.WIPE_IN_OUT,
    Mode.COMPRESSED_ROTATE: Capability.COMPRESSED_ROTATE,
    Mode.EXPLODE: Capability.EXPLODE,
    Mode.CLOCK: Capability.CLOCK,
}

_SPECIAL_MODES = {
    SpecialMode.TWINKLE: Capability.TWINKLE,
    SpecialMode.SPARKLE: Capability.SPARKLE,
    SpecialMode.SNOW: Capability.SNOW,
    SpecialMode.INTERLOCK: Capability.INTERLOCK,
    SpecialMode.SWITCH: Capability.SWITCH,
    SpecialMode.SLIDE: Capability.SLIDE,
    SpecialMode.SPRAY: Capability.SPRAY,
    SpecialMode.STARBURST: Capability.STARBURST,
    # Table 66 marks these two as animations.
    SpecialMode.WELCOME: Capability.ANIMATION,
    SpecialMode.SLOT_MACHINE: Capability.ANIMATION,
    SpecialMode.NEWS_FLASH: Capability.BETABRITE_1036_ANIMATIONS,
    SpecialMode.TRUMPET: Capability.BETABRITE_1036_ANIMATIONS,
    SpecialMode.CYCLE_COLORS: Capability.CYCLE_COLORS,
}

_FONTS = {
    Font.FIVE_HIGH: Capability.FONT_FIVE_HIGH,
    Font.SEVEN_HIGH: Capability.FONT_SEVEN_HIGH,
    Font.SEVEN_HIGH_FANCY: Capability.FONT_SEVEN_HIGH_FANCY,
    Font.TEN_HIGH: Capability.FONT_TEN_HIGH,
    Font.FULL_HEIGHT_FANCY: Capability.FONT_FULL_HEIGHT_FANCY,
    Font.FULL_HEIGHT: Capability.FONT_FULL_HEIGHT,
    # Appendix G, p. 82, note 1: "only applies to Betabrite model 1036 signs."
    Font.FIVE_STROKE: Capability.BETABRITE_1036_FONTS,
    Font.SEVEN_STROKE: Capability.BETABRITE_1036_FONTS,
    Font.SEVEN_SHADOW: Capability.BETABRITE_1036_FONTS,
    Font.SEVEN_SHADOW_FANCY: Capability.BETABRITE_1036_FONTS,
    Font.FIVE_WIDE: Capability.BETABRITE_1036_FONTS,
    Font.SEVEN_WIDE: Capability.BETABRITE_1036_FONTS,
    Font.SEVEN_FANCY_WIDE: Capability.BETABRITE_1036_FONTS,
    Font.WIDE_STROKE_FIVE: Capability.BETABRITE_1036_FONTS,
}

_ATTRIBUTES = {
    Attribute.WIDE: Capability.WIDE,
    Attribute.DOUBLE_WIDE: Capability.DOUBLE_WIDE,
    Attribute.DOUBLE_HIGH: Capability.DOUBLE_HIGH,
    Attribute.TRUE_DESCENDERS: Capability.TRUE_DESCENDERS,
    Attribute.FIXED_WIDTH: Capability.FIXED_WIDTH,
}


def _capability(code: object) -> Capability | None:
    match code:
        case Mode():
            return _MODES[code]
        case SpecialMode():
            return _SPECIAL_MODES[code]
        case SpecialGraphic():
            return Capability.ANIMATION
        case Position.LEFT | Position.RIGHT:
            return Capability.LEFT_RIGHT_POSITION
        case Font():
            return _FONTS[code]
        case Color():
            return Capability.COLOR
        case Speed():
            return Capability.SPEED
        case Control.NEW_LINE:
            return Capability.NEW_LINE
        case Control.NEW_PAGE:
            return Capability.NEW_PAGE
        case Wide():
            return Capability.WIDE
        case DoubleHigh():
            return Capability.DOUBLE_HIGH
        case TrueDescenders():
            return Capability.TRUE_DESCENDERS
        case CharacterFlash():
            return Capability.CHARACTER_FLASH
        case CharacterAttribute(attribute=attribute):
            return _ATTRIBUTES.get(attribute)
        case Spacing.FIXED_WIDTH:
            return Capability.FIXED_WIDTH
        case CurrentTime():
            return Capability.TIME
        case CurrentDate():
            return Capability.DATE
        case StringRef():
            return Capability.STRING
        case _:
            return None
