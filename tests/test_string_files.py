"""STRING Files: live values that update without blanking the display (pp. 37, 53)."""

import pytest

from alpha_led_sign.protocol.codes import (
    CharacterFlash,
    Color,
    Control,
    ControlCode,
    CurrentDate,
    CurrentTime,
    DoubleHigh,
    Font,
    Spacing,
    Speed,
    StringRef,
    Wide,
)
from alpha_led_sign.protocol.commands import STRING_MAX_BYTES, WriteString
from alpha_led_sign.protocol.packet import Recipient, encode_packet

SYNC = b"\x00" * 5
ALL_SIGNS = Recipient("Z", 0)


def test_write_string_file_matches_table_57() -> None:
    packet = encode_packet(ALL_SIGNS, [WriteString("1", "7,345")], checksum=False)

    assert bytes(packet) == SYNC + b"\x01Z00\x02G17,345\x04"


def test_string_files_take_the_control_codes_table_19_allows() -> None:
    content = [
        Speed.NO_HOLD,
        Wide(True),
        Font.SEVEN_HIGH,
        Color.AMBER,
        Spacing.FIXED_WIDTH,
        "72",
        Control.NEW_LINE,
        CurrentTime(),
    ]

    data = WriteString("T", content).encode_data()

    assert data == b"T\x09\x12\x1a3\x1c3\x1e172\x0d\x13"


@pytest.mark.parametrize(
    "code",
    [
        Color.RAINBOW_1,
        Color.RAINBOW_2,
        Control.NEW_PAGE,
        CurrentDate(),
        StringRef("U"),
        DoubleHigh(),
        CharacterFlash(),
    ],
)
def test_string_files_reject_other_control_codes(code: ControlCode) -> None:
    with pytest.raises(ValueError, match="STRING File"):
        WriteString("T", ["x", code])


def test_string_file_data_is_at_most_125_bytes() -> None:
    # p. 37: STRING File data is buffered, so it is limited to 125 bytes.
    assert STRING_MAX_BYTES == 125
    WriteString("T", "x" * 125)

    with pytest.raises(ValueError, match="125 bytes"):
        WriteString("T", [Color.RED, "x" * 124])
