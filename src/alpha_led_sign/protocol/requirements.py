"""Requirements: what each Command and code needs from a Sign Model.

The Capabilities are the columns of Tables 68-70; the Protocol Versions come from
the tables that list each code.
"""

from dataclasses import dataclass

from alpha_led_sign.protocol.capabilities import Capability
from alpha_led_sign.protocol.codes import Font, Mode, Position, SpecialGraphic, SpecialMode
from alpha_led_sign.protocol.control_codes import kind_of
from alpha_led_sign.protocol.memory import MemoryFile
from alpha_led_sign.protocol.versions import ProtocolVersion


@dataclass(frozen=True)
class VersionRequirement:
    """A Command or code needs a Sign that accepts a Protocol Version or a later one.

    Attributes:
        version: The earliest Protocol Version that will do.
        source: The Command or code that needs it.
    """

    version: ProtocolVersion
    source: object


@dataclass(frozen=True)
class CapabilityRequirement:
    """A Command or code needs a Sign Model with a Capability.

    Attributes:
        capability: The Capability.
        source: The Command or code that needs it.
    """

    capability: Capability
    source: object


@dataclass(frozen=True)
class DisplaySizeRequirement:
    """A Command needs a display at least this large (Table 70, note 1).

    Attributes:
        columns: The width needed, in pixels.
        rows: The height needed, in pixels.
        source: The Command that needs it.
    """

    columns: int
    rows: int
    source: object


@dataclass(frozen=True)
class MemoryRequirement:
    """A Memory Configuration must fit the Sign's memory (p. 27, note 1).

    Attributes:
        files: The Files of the Memory Configuration.
    """

    files: tuple[MemoryFile, ...]


@dataclass(frozen=True)
class FontPositionRequirement:
    """A font taller than 7 rows is shown in a Display Position.

    A two-line Sign "will 'size down'" such a font outside the Middle position
    (p. 96, 7.10.3.2.5), so the Sign Model decides whether it shows as written.

    Attributes:
        font: The tall font.
        position: The Display Position of its Frame.
    """

    font: Font
    position: Position


type Requirement = (
    VersionRequirement
    | CapabilityRequirement
    | DisplaySizeRequirement
    | MemoryRequirement
    | FontPositionRequirement
)
"""One thing a Command or code needs from a Sign Model to be shown as written."""


TALL_FONTS = frozenset({Font.TEN_HIGH, Font.FULL_HEIGHT, Font.FULL_HEIGHT_FANCY})
"""Fonts taller than 7 rows (Appendix G, p. 82; Appendix O)."""


def requires(code: object) -> tuple[Requirement, ...]:
    """List what a code needs from a Sign Model.

    Codes the manual does not mark with a version work with every version, so they
    have no VersionRequirement. Codes every Sign has have no CapabilityRequirement.

    Args:
        code: A Mode, Special Mode, Special Graphic, Display Position, or Control
            Code.

    Returns:
        The Requirements, possibly none.

    Examples:
        >>> from alpha_led_sign.protocol import Mode, requires
        >>> [type(found).__name__ for found in requires(Mode.EXPLODE)]
        ['VersionRequirement', 'CapabilityRequirement']
    """
    found: list[Requirement] = []
    version = _MIN_VERSIONS.get(code, ProtocolVersion.EZ_KEY_II)
    if version > ProtocolVersion.EZ_KEY_II:
        found.append(VersionRequirement(version, code))
    capability = _capability(code)
    if capability is not None:
        found.append(CapabilityRequirement(capability, code))
    return tuple(found)


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


def _capability(code: object) -> Capability | None:
    match code:
        case Mode():
            return _MODES[code]
        case SpecialMode():
            return _SPECIAL_MODES[code]
        case SpecialGraphic():
            return Capability.ANIMATION  # Table 66
        case Position.LEFT | Position.RIGHT:
            return Capability.LEFT_RIGHT_POSITION
        case _:
            kind = kind_of(code)
            return None if kind is None else kind.capability(code)
