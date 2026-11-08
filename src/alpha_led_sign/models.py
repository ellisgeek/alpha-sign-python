"""Sign Models: what each product is and which Capabilities it has.

A Sign Model is data. Adding a model means adding one entry here.
"""

import json
import warnings
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from importlib import resources

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
    min_version,
)
from alpha_led_sign.protocol.commands import Command
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


# Matrix column -> Capability. Columns that split one Capability by direction
# (horizontal/vertical, whole/half display) map to the same Capability.
_COLUMNS = {
    "Automode": Capability.AUTOMODE,
    "Flash": Capability.FLASH,
    "Hold": Capability.HOLD,
    "Interlock": Capability.INTERLOCK,
    "Roll: Up/Down/Left/Right": Capability.ROLL,
    "Roll: In/Out (horizontal)": Capability.ROLL_IN_OUT,
    "Roll: In/Out (vertical)": Capability.ROLL_IN_OUT,
    "Rotate: Standard": Capability.ROTATE,
    "Rotate: Condensed": Capability.COMPRESSED_ROTATE,
    "Scroll": Capability.SCROLL,
    "Slide": Capability.SLIDE,
    "Cycle Color": Capability.CYCLE_COLORS,
    "Snow": Capability.SNOW,
    "Sparkle": Capability.SPARKLE,
    "Spray": Capability.SPRAY,
    "Starburst": Capability.STARBURST,
    "Switch: Switch": Capability.SWITCH,
    "Switch: Switch half the display": Capability.SWITCH,
    "Twinkle": Capability.TWINKLE,
    "Wipe: Up/Down/Left/Right": Capability.WIPE,
    "Wipe: In /Out (horizontal)": Capability.WIPE_IN_OUT,
    "Wipe: In/Out (vertical)": Capability.WIPE_IN_OUT,
    "Explode": Capability.EXPLODE,
    "Clock": Capability.CLOCK,
    "Left/Right Display Position": Capability.LEFT_RIGHT_POSITION,
    "15/16 Row Normal": Capability.FONT_FULL_HEIGHT,
    "15/16 Row Fancy": Capability.FONT_FULL_HEIGHT_FANCY,
    "Ten Row": Capability.FONT_TEN_HIGH,
    "Seven Row Normal": Capability.FONT_SEVEN_HIGH,
    "Seven Row Fancy": Capability.FONT_SEVEN_HIGH_FANCY,
    "Five Row": Capability.FONT_FIVE_HIGH,
    "Color [1]": Capability.COLOR,
    "Normal": None,  # plain characters: always available
    "Wide": Capability.WIDE,
    "Double Wide": Capability.DOUBLE_WIDE,
    "Flashing": Capability.CHARACTER_FLASH,
    "Double Height": Capability.DOUBLE_HIGH,
    "True Descenders": Capability.TRUE_DESCENDERS,
    "Fixed Width": Capability.FIXED_WIDTH,
    "Time": Capability.TIME,
    "Date": Capability.DATE,
    "Temperature: Fahrenheit": Capability.TEMPERATURE_FAHRENHEIT,
    "Temperature: Celsius": Capability.TEMPERATURE_CELSIUS,
    "Speed": Capability.SPEED,
    "New Line": Capability.NEW_LINE,
    "New Page": Capability.NEW_PAGE,
    "Animation": Capability.ANIMATION,
    "String": Capability.STRING,
    "Ticker Symbol": Capability.TICKER_SYMBOL,
    "Variable": Capability.VARIABLE,
    "Counter": Capability.COUNTER,
    "Graphic [1]": Capability.GRAPHIC,
    "Gif [1]": Capability.GIF,
    "Flick [1]": Capability.FLICK,
    "Message": Capability.MESSAGE,
}


def _load_matrices() -> dict[str, frozenset[Capability]]:
    """Read Tables 68-70 into {matrix row name: Capabilities}.

    A cell with a footnote (such as "1") counts as supported; the footnotes only
    qualify how.
    """
    text = resources.files("alpha_led_sign").joinpath("capability-matrices.json").read_text()
    rows: dict[str, set[Capability]] = {}
    for table in json.loads(text):
        for row, cells in table["rows"].items():
            found = rows.setdefault(row, set())
            for column, value in cells.items():
                capability = _COLUMNS[column]
                if value and capability is not None:
                    found.add(capability)
    return {row: frozenset(found) for row, found in rows.items()}


MATRIX_ROWS = _load_matrices()
"""Capabilities per row of Tables 68-70, keyed by the row name the manual uses."""

_EZ_KEY_II_AND_ALPHA_1 = frozenset({ProtocolVersion.EZ_KEY_II, ProtocolVersion.ALPHA_1_0})


@dataclass(frozen=True)
class SignModel:
    """A product such as the 4120C. ``None`` means the value is unknown."""

    name: str
    sign_type: str
    """Table 5, p. 10."""
    series: str | None
    columns: int | None
    rows: int | None
    lines: int | None
    memory_bytes: int | None
    max_messages: int | None
    protocol_versions: frozenset[ProtocolVersion]
    """Table 3, p. 8."""
    capabilities: frozenset[Capability] | None
    """``None`` means unknown: no Capability checks for this model."""


_COLORS = frozenset({Capability.COLOR})


def _series_4000(name: str, sign_type: str, columns: int) -> SignModel:
    capabilities = MATRIX_ROWS["4000 Series"]
    if name.endswith("R"):
        capabilities -= _COLORS  # Table 69, note 1: red only.
    return SignModel(
        name=name,
        sign_type=sign_type,
        series="4000 Series",
        columns=columns,  # brochure: N x 16 pixels, 2 lines, 28,000 bytes, 81 messages
        rows=16,
        lines=2,
        memory_bytes=28_000,
        max_messages=81,
        protocol_versions=_EZ_KEY_II_AND_ALPHA_1,
        capabilities=capabilities,
    )


ALPHA_4080C = _series_4000("4080C", "t", 80)
ALPHA_4120C = _series_4000("4120C", "a", 120)
ALPHA_4120R = _series_4000("4120R", "g", 120)
ALPHA_4160C = _series_4000("4160C", "b", 160)
ALPHA_4160R = _series_4000("4160R", "h", 160)
ALPHA_4200C = _series_4000("4200C", "c", 200)
ALPHA_4200R = _series_4000("4200R", "i", 200)
ALPHA_4240C = _series_4000("4240C", "d", 240)
ALPHA_4240R = _series_4000("4240R", "j", 240)

BETABRITE = SignModel(
    name="BetaBrite",
    sign_type="^",
    series=None,
    columns=None,
    rows=None,
    lines=1,
    memory_bytes=None,
    max_messages=None,
    protocol_versions=_EZ_KEY_II_AND_ALPHA_1,
    capabilities=MATRIX_ROWS["BetaBrite"],
)

GENERIC = SignModel(
    name="Generic",
    sign_type="Z",  # all signs
    series=None,
    columns=None,
    rows=None,
    lines=None,
    memory_bytes=None,
    max_messages=None,
    protocol_versions=frozenset({ProtocolVersion.ALPHA_1_0}),
    capabilities=None,
)
"""Any Alpha sign without a profile: Alpha 1.0, no Capability checks."""

REGISTRY: dict[str, SignModel] = {
    model.name: model
    for model in (
        ALPHA_4080C,
        ALPHA_4120C,
        ALPHA_4120R,
        ALPHA_4160C,
        ALPHA_4160R,
        ALPHA_4200C,
        ALPHA_4200R,
        ALPHA_4240C,
        ALPHA_4240R,
        BETABRITE,
        GENERIC,
    )
}


def get(name: str) -> SignModel:
    """Look up a Sign Model by name, such as ``"4120C"``."""
    try:
        return REGISTRY[name]
    except KeyError:
        raise KeyError(f"unknown Sign Model {name!r}; known: {', '.join(REGISTRY)}") from None


class UnsupportedCapability(Exception):  # noqa: N818 (name fixed by docs/plan.md)
    """Raised by strict validation when a Sign Model lacks something a Command uses."""


class UnsupportedCapabilityWarning(UserWarning):
    """Warned by advisory validation when a Sign Model lacks something a Command uses."""


def validate(model: SignModel, commands: Sequence[Command], *, strict: bool = False) -> None:
    """Check ``commands`` against what ``model`` supports.

    Strict validation raises UnsupportedCapability listing every problem. Advisory
    validation (the default) warns once per problem, because the manual's tables
    have gaps and the Sign may well accept the Command anyway.
    """
    problems = [problem for command in commands for problem in _problems(model, command)]
    if strict and problems:
        raise UnsupportedCapability("; ".join(problems))
    for problem in problems:
        warnings.warn(problem, UnsupportedCapabilityWarning, stacklevel=2)


def _problems(model: SignModel, command: Command) -> list[str]:
    newest = max(model.protocol_versions)
    problems: list[str] = []
    if command.min_version > newest:
        problems.append(_version_problem(model, command.min_version, command))
    for code in command.codes():
        if min_version(code) > newest:
            problems.append(_version_problem(model, min_version(code), code))
        capability = required_capability(code)
        if model.capabilities is None or capability is None:
            continue
        if capability not in model.capabilities:
            problems.append(f"{model.name} does not support {capability.value} ({_describe(code)})")
    return problems


def _version_problem(model: SignModel, needed: ProtocolVersion, item: object) -> str:
    return f"{model.name} does not accept {needed.label}, which {_describe(item)} needs"


def _describe(item: object) -> str:
    if isinstance(item, Enum):
        return f"{type(item).__name__}.{item.name}"
    if isinstance(item, Command):
        return type(item).__name__
    return repr(item)


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
    # The rest are marked "BetaBrite model 1036 only" in Appendix G.
}

_ATTRIBUTES = {
    Attribute.WIDE: Capability.WIDE,
    Attribute.DOUBLE_WIDE: Capability.DOUBLE_WIDE,
    Attribute.DOUBLE_HIGH: Capability.DOUBLE_HIGH,
    Attribute.TRUE_DESCENDERS: Capability.TRUE_DESCENDERS,
    Attribute.FIXED_WIDTH: Capability.FIXED_WIDTH,
}


def required_capability(code: object) -> Capability | None:
    """The Capability a Sign Model needs to use ``code``, or None if none is known."""
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
            return _FONTS.get(code, Capability.BETABRITE_1036_FONTS)
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
