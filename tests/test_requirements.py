"""What each Mode, Display Position, and Control Code needs from a Sign Model."""

import pytest

from alpha_led_sign.protocol.codes import (
    DotsPictureRef,
    Font,
    Mode,
    Position,
    SpecialGraphic,
    SpecialMode,
)
from alpha_led_sign.protocol.requirements import Capability, Requirement, requires
from alpha_led_sign.protocol.versions import ProtocolVersion


@pytest.mark.parametrize(
    ("code", "needs"),
    [
        (Mode.EXPLODE, (ProtocolVersion.ALPHA_3_0, Capability.EXPLODE)),  # Tables 65, 68
        (Position.LEFT, (ProtocolVersion.ALPHA_3_0, Capability.LEFT_RIGHT_POSITION)),  # 12, 68
        (Position.TOP, (ProtocolVersion.EZ_KEY_II, None)),  # Table 12
        (SpecialGraphic.FIREWORKS, (ProtocolVersion.EZ_KEY_II, Capability.ANIMATION)),  # 66
        # p. 81; Table 70's Graphic column.
        (DotsPictureRef("A"), (ProtocolVersion.EZ_KEY_II, Capability.GRAPHIC)),
    ],
)
def test_codes_need_what_the_manual_says(
    code: object, needs: tuple[ProtocolVersion, Capability | None]
) -> None:
    assert requires(code) == Requirement(*needs)


def test_a_requirement_names_its_version_and_capability() -> None:
    needs = requires(Mode.EXPLODE)

    assert (needs.version, needs.capability) == (ProtocolVersion.ALPHA_3_0, Capability.EXPLODE)


@pytest.mark.parametrize(
    "font",
    [
        Font.FIVE_STROKE,
        Font.SEVEN_STROKE,
        Font.SEVEN_SHADOW,
        Font.SEVEN_SHADOW_FANCY,
        Font.FIVE_WIDE,
        Font.SEVEN_WIDE,
        Font.SEVEN_FANCY_WIDE,
        Font.WIDE_STROKE_FIVE,
    ],
    ids=repr,
)
def test_fonts_marked_betabrite_1036_only_need_its_fonts(font: Font) -> None:
    # Appendix G, p. 82, note 1: "only applies to Betabrite model 1036 signs."
    assert requires(font).capability is Capability.BETABRITE_1036_FONTS


@pytest.mark.parametrize(
    "code",
    [*Mode, *SpecialMode, *Font],
    ids=repr,
)
def test_every_mode_special_mode_and_font_has_an_entry(code: object) -> None:
    # Each is a column of Tables 68-70 or a footnoted Appendix G entry, looked up by
    # member, so a new member without an entry fails here instead of in Sign.send.
    assert requires(code).capability is not None
