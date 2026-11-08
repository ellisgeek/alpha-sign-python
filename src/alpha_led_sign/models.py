"""Sign Models: what each product is and which Capabilities it has.

A Sign Model is data. Adding a model means adding one entry here.
"""

import json
import warnings
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from importlib import resources

from alpha_led_sign.protocol.commands import Command
from alpha_led_sign.protocol.requirements import Capability, requires
from alpha_led_sign.protocol.versions import ProtocolVersion

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


class UnsupportedCapability(Exception):  # noqa: N818 (public name, docs/spec.md)
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
        version, capability = requires(code)
        if version > newest:
            problems.append(_version_problem(model, version, code))
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
