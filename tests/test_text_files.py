"""TEXT Files: Messages, Frames, and Control Codes, checked against the manual."""

import pytest

from alpha_led_sign.protocol.codes import (
    Attribute,
    CharacterAttribute,
    CharacterFlash,
    Color,
    Control,
    ControlCode,
    CurrentDate,
    CurrentTime,
    DateFormat,
    DotsPictureRef,
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
from alpha_led_sign.protocol.commands import PRIORITY_LABEL, WriteText
from alpha_led_sign.protocol.message import Frame, Message
from alpha_led_sign.protocol.packet import Recipient, encode_packet

SYNC = b"\x00" * 5
ALL_SIGNS = Recipient("Z", 0)


def test_rotate_on_the_bottom_line_matches_table_47() -> None:
    message = Message(Frame(Mode.ROTATE, Position.BOTTOM, "HELLO"))

    packet = encode_packet(ALL_SIGNS, [WriteText("D", message)], checksum=False)

    assert bytes(packet) == SYNC + b"\x01Z00\x02AD\x1b&aHELLO\x04"


def test_special_modes_and_a_trailing_mode_match_table_48() -> None:
    message = Message(
        Frame(SpecialMode.SNOW, Position.TOP, "Hello There"),
        Frame(Mode.ROTATE, Position.TOP),
        Frame(SpecialMode.WELCOME, Position.BOTTOM),
    )

    packet = encode_packet(ALL_SIGNS, [WriteText(">", message)], checksum=False)

    assert bytes(packet) == SYNC + b'\x01Z00\x02A>\x1b"n2Hello There\x1b"a\x1b&n8\x04'


def test_priority_text_file_with_a_font_matches_table_50() -> None:
    message = Message(Frame(Mode.FLASH, Position.MIDDLE, [Font.FULL_HEIGHT, "EMERGENCY"]))

    packet = encode_packet(ALL_SIGNS, [WriteText(PRIORITY_LABEL, message)], checksum=False)

    assert bytes(packet) == SYNC + b"\x01Z00\x02A0\x1b c\x1a9EMERGENCY\x04"


def test_empty_priority_text_file_disables_it_matching_table_51() -> None:
    packet = encode_packet(ALL_SIGNS, [WriteText(PRIORITY_LABEL, Message())], checksum=False)

    assert bytes(packet) == SYNC + b"\x01Z00\x02A0\x04"


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        (Color.RED, b"\x1c1"),
        (Color.GREEN, b"\x1c2"),
        (Color.AMBER, b"\x1c3"),
        (Color.RAINBOW_2, b"\x1cA"),
        (Color.AUTOCOLOR, b"\x1cC"),
        (Font.FIVE_HIGH, b"\x1a1"),
        (Font.WIDE_STROKE_FIVE, b"\x1a>"),
        (Speed.SPEED_1, b"\x15"),
        (Speed.SPEED_5, b"\x19"),
        (Speed.NO_HOLD, b"\x09"),
        (Control.NEW_LINE, b"\x0d"),
        (Control.NEW_PAGE, b"\x0c"),
        (Wide(True), b"\x12"),
        (Wide(False), b"\x11"),
        (DoubleHigh(True), b"\x051"),
        (TrueDescenders(False), b"\x060"),
        (CharacterFlash(True), b"\x071"),
        (CharacterAttribute(Attribute.DOUBLE_WIDE, True), b"\x1d11"),
        (CharacterAttribute(Attribute.FIXED_WIDTH, False), b"\x1d40"),
        (Spacing.FIXED_WIDTH, b"\x1e1"),
        (CurrentTime(), b"\x13"),
        (CurrentDate(DateFormat.MM_DD_YY_SLASH), b"\x0b0"),
        (CurrentDate(DateFormat.DAY_OF_WEEK), b"\x0b9"),
        (StringRef("T"), b"\x10T"),
        (DotsPictureRef("A"), b"\x14A"),  # p. 81: Call SMALL DOTS PICTURE
    ],
)
def test_control_codes_match_appendix_g(code: ControlCode, expected: bytes) -> None:
    assert Frame(Mode.HOLD, Position.FILL, [code]).encode() == b"\x1b0b" + expected


def test_special_graphic_is_mode_code_n_and_its_specifier_from_table_67() -> None:
    assert Frame(SpecialGraphic.FIREWORKS, Position.TOP).encode() == b'\x1b"nX'


def test_special_graphic_frame_cannot_have_text() -> None:
    # Table 12 note: text after a Special Graphic needs another Mode Field.
    with pytest.raises(ValueError, match="Special Graphic"):
        Frame(SpecialGraphic.THANK_YOU, Position.FILL, "Come again")


@pytest.mark.parametrize("text", ["line one\nline two", "\x1c1red", "café"])
def test_literal_text_must_be_printable_ascii(text: str) -> None:
    with pytest.raises(ValueError, match="printable ASCII"):
        Frame(Mode.HOLD, Position.FILL, ["ok", text])


def test_literal_text_may_use_the_whole_standard_character_set() -> None:
    # Appendix G, p. 83: 20H-7FH are displayable (7EH is a half space, 7FH a block).
    text = "".join(chr(c) for c in range(0x20, 0x80))

    # Each displayable character is its own byte, 20H-7FH in order.
    assert Frame(Mode.HOLD, Position.FILL, text).encode() == b"\x1b0b" + bytes(range(0x20, 0x80))


@pytest.mark.parametrize("label", ["", "AB", "\x1f", "\x7f", "é"])
def test_file_labels_are_one_character_from_20h_to_7eh(label: str) -> None:
    # Appendix A, p. 50.
    with pytest.raises(ValueError, match="File Label"):
        WriteText(label, Message())
    with pytest.raises(ValueError, match="File Label"):
        StringRef(label)


def test_priority_text_file_holds_at_most_125_bytes() -> None:
    # p. 20. The Mode Field (ESC, position, mode) counts toward the 125 bytes.
    WriteText(PRIORITY_LABEL, Message(Frame(Mode.HOLD, Position.FILL, "x" * 122)))

    with pytest.raises(ValueError, match="125 bytes"):
        WriteText(PRIORITY_LABEL, Message(Frame(Mode.HOLD, Position.FILL, "x" * 123)))
