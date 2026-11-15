"""What each Command and code needs from a Sign Model."""

import pytest

from alpha_led_sign.protocol.codes import (
    Attribute,
    CharacterAttribute,
    Color,
    DotsPictureRef,
    Font,
    Mode,
    Position,
    SpecialGraphic,
    SpecialMode,
)
from alpha_led_sign.protocol.commands import (
    ClearMemory,
    SetMemoryConfiguration,
    WriteDotsPicture,
    WriteString,
    WriteText,
)
from alpha_led_sign.protocol.memory import TextFile
from alpha_led_sign.protocol.message import Frame, Message
from alpha_led_sign.protocol.pictures import DotsPicture, PixelColor
from alpha_led_sign.protocol.requirements import (
    Capability,
    CapabilityRequirement,
    DisplaySizeRequirement,
    FontPositionRequirement,
    MemoryRequirement,
    VersionRequirement,
    requires,
)
from alpha_led_sign.protocol.versions import ProtocolVersion


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        # Tables 65, 68.
        (
            Mode.EXPLODE,
            (
                VersionRequirement(ProtocolVersion.ALPHA_3_0, Mode.EXPLODE),
                CapabilityRequirement(Capability.EXPLODE, Mode.EXPLODE),
            ),
        ),
        # Tables 12, 68.
        (
            Position.LEFT,
            (
                VersionRequirement(ProtocolVersion.ALPHA_3_0, Position.LEFT),
                CapabilityRequirement(Capability.LEFT_RIGHT_POSITION, Position.LEFT),
            ),
        ),
        (Position.TOP, ()),  # Table 12: every Sign, every version.
        # Table 66.
        (
            SpecialGraphic.FIREWORKS,
            (CapabilityRequirement(Capability.ANIMATION, SpecialGraphic.FIREWORKS),),
        ),
        # p. 81; Table 70's Graphic column.
        (
            DotsPictureRef("A"),
            (CapabilityRequirement(Capability.GRAPHIC, DotsPictureRef("A")),),
        ),
    ],
)
def test_codes_need_what_the_manual_says(code: object, expected: tuple[object, ...]) -> None:
    assert requires(code) == expected


def capabilities(code: object) -> set[Capability]:
    return {r.capability for r in requires(code) if isinstance(r, CapabilityRequirement)}


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
    assert capabilities(font) == {Capability.BETABRITE_1036_FONTS}


@pytest.mark.parametrize(
    "code",
    [*Mode, *SpecialMode, *Font],
    ids=repr,
)
def test_every_mode_special_mode_and_font_has_an_entry(code: object) -> None:
    # Each is a column of Tables 68-70 or a footnoted Appendix G entry, looked up by
    # member, so a new member without an entry fails here instead of in Sign.send.
    assert capabilities(code)


@pytest.mark.parametrize(
    ("attribute", "capability"),
    [
        # Appendix G, p. 82: "Auxiliary Port ON or OFF (Series 4000 & 7000 signs only.)"
        (Attribute.AUXILIARY_PORT, Capability.AUXILIARY_PORT),
        # Appendix G, p. 82: "Shadow characters ON or OFF (Betabrite model 1036 and
        # AlphaPremiere 9000 signs only)"
        (Attribute.SHADOW, Capability.SHADOW),
    ],
)
def test_attributes_limited_to_some_signs_need_their_capability(
    attribute: Attribute, capability: Capability
) -> None:
    for on in (True, False):
        assert capabilities(CharacterAttribute(attribute, on)) == {capability}


def test_a_command_with_no_codes_requires_nothing() -> None:
    assert tuple(ClearMemory().requirements()) == ()


def test_a_text_file_write_requires_what_its_codes_require() -> None:
    command = WriteText("A", Message(Frame(Mode.EXPLODE, Position.FILL, [Color.RED, "x"])))

    assert set(command.requirements()) == {
        VersionRequirement(ProtocolVersion.ALPHA_3_0, Mode.EXPLODE),
        CapabilityRequirement(Capability.EXPLODE, Mode.EXPLODE),
        CapabilityRequirement(Capability.COLOR, Color.RED),
    }


def test_a_string_file_write_requires_what_its_codes_require() -> None:
    assert set(WriteString("T", [Color.RED, "x"]).requirements()) == {
        CapabilityRequirement(Capability.COLOR, Color.RED)
    }


@pytest.mark.parametrize("font", [Font.TEN_HIGH, Font.FULL_HEIGHT, Font.FULL_HEIGHT_FANCY])
def test_a_font_taller_than_seven_rows_requires_room_in_its_display_position(font: Font) -> None:
    # p. 96, 7.10.3.2.5: whether a tall font shows at full size depends on the position.
    command = WriteText("A", Message(Frame(Mode.HOLD, Position.TOP, [font, "x"])))

    assert FontPositionRequirement(font, Position.TOP) in set(command.requirements())


def test_a_seven_row_font_has_no_position_requirement() -> None:
    command = WriteText("A", Message(Frame(Mode.HOLD, Position.TOP, [Font.SEVEN_HIGH, "x"])))

    assert not any(isinstance(r, FontPositionRequirement) for r in command.requirements())


def test_a_memory_configuration_requires_room_for_its_files() -> None:
    files = (TextFile("A", 100), TextFile("B", 0))

    assert tuple(SetMemoryConfiguration(files).requirements()) == (MemoryRequirement(files),)


def test_a_dots_picture_write_requires_the_graphic_capability_and_room_on_the_display() -> None:
    # Table 70: pictures need the Graphic column; note 1: they must fit the display.
    command = WriteDotsPicture("P", DotsPicture.parse("12\n30"))

    assert set(command.requirements()) == {
        CapabilityRequirement(Capability.GRAPHIC, command),
        DisplaySizeRequirement(2, 2, command),
        CapabilityRequirement(Capability.COLOR, PixelColor.GREEN),
        CapabilityRequirement(Capability.COLOR, PixelColor.AMBER),
    }


def test_a_red_dots_picture_does_not_require_color() -> None:
    # Table 69, note 1: an R model shows red, so red and off need no color.
    command = WriteDotsPicture("P", DotsPicture.parse("10\n01"))

    assert CapabilityRequirement(Capability.COLOR, PixelColor.RED) not in set(
        command.requirements()
    )
