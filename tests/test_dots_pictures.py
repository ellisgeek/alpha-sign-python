"""SMALL DOTS PICTURE Files: pictures a TEXT File can call (pp. 39-41, 76, 81)."""

import warnings
from dataclasses import replace

import pytest

from alpha_led_sign import Sign, SignTimeoutError, models
from alpha_led_sign.models import UnsupportedCapability, UnsupportedCapabilityWarning, validate
from alpha_led_sign.protocol.codes import DotsPictureRef, Mode
from alpha_led_sign.protocol.commands import ReadDotsPicture, WriteDotsPicture, WriteText
from alpha_led_sign.protocol.message import Frame, Message
from alpha_led_sign.protocol.packet import Chunk, Recipient, encode_packet
from alpha_led_sign.protocol.pictures import DotsPicture
from alpha_led_sign.protocol.requirements import Capability
from alpha_led_sign.protocol.response import ResponseError, ResponseItem, UnexpectedResponseError
from tests.fakes import FakeTransport

SYNC = b"\x00" * 5

# Table 60, p. 76: a 15 x 9 arrow, written to DOTS PICTURE File "A" of every 4160C.
TABLE_60_ROWS = [
    "000000000",
    "000000000",
    "000100000",
    "000110000",
    "000111000",
    "000111100",
    "111111110",
    "111111112",
    "111111110",
    "000111100",
    "000111000",
    "000110000",
    "000100000",
    "000000000",
    "000000000",
]
TABLE_60 = (
    SYNC
    + b"\x01b00\x02IA0F09"
    + b"".join(row.encode("ascii") + b"\r" for row in TABLE_60_ROWS)
    + b"\x04"
)


def test_write_dots_picture_matches_table_60() -> None:
    picture = DotsPicture.parse("\n".join(TABLE_60_ROWS))

    packet = encode_packet(Recipient("b", 0), [WriteDotsPicture("A", picture)], checksum=False)

    assert bytes(packet) == TABLE_60


def test_write_dots_picture_pauses_100_ms_after_the_width() -> None:
    # p. 40: "Following the Width bytes, there should be at least a 100 millisecond delay
    # ... before sending the Row Bit Pattern."
    picture = DotsPicture.parse("12\n03")

    packet = encode_packet(Recipient("b", 0), [WriteDotsPicture("A", picture)], checksum=False)

    assert packet.chunks == (
        Chunk(SYNC + b"\x01b00\x02IA0202", pause_after=0.1),
        Chunk(b"12\r03\r\x04"),
    )


def test_write_dots_picture_pauses_after_the_width_inside_a_nested_packet() -> None:
    picture = DotsPicture.parse("1")
    commands = [WriteText("A", Message(Frame(None, content="X"))), WriteDotsPicture("B", picture)]

    packet = encode_packet(Recipient("b", 0), commands, checksum=False)

    # p. 11: 100 ms after each STX of a nested Packet; p. 40: 100 ms after the Width.
    assert packet.chunks == (
        Chunk(SYNC + b"\x01b00\x02", pause_after=0.1),
        Chunk(b"AAX\x03\x02", pause_after=0.1),
        Chunk(b"IB0101", pause_after=0.1),
        Chunk(b"1\r\x03\x04"),
    )


@pytest.mark.parametrize(
    ("text", "match"),
    [
        ("\n".join(["0"] * 32), "at most 31 rows"),  # p. 39
        ("0" * 256, "at most 255 columns"),  # p. 40
        ("00\n0", "as wide"),
        ("09", "PixelColor"),  # p. 40: "0"-"8" only
        ("0R", "PixelColor"),
    ],
)
def test_dots_picture_refuses_what_the_protocol_cannot_send(text: str, match: str) -> None:
    with pytest.raises(ValueError, match=match):
        DotsPicture.parse(text)


def test_dots_picture_takes_the_largest_small_picture() -> None:
    picture = DotsPicture.parse("\n".join(["8" * 255] * 31))

    assert (picture.height, picture.width) == (31, 255)


def test_write_dots_picture_refuses_a_bad_file_label() -> None:
    with pytest.raises(ValueError, match="File Label"):
        WriteDotsPicture("\x7f", DotsPicture.parse("1"))


def test_read_dots_picture_asks_with_command_code_j() -> None:
    packet = encode_packet(Recipient("b", 1), [ReadDotsPicture("A")], checksum=False)

    # Table 23, p. 41: "J" and the File Label.
    assert bytes(packet) == SYNC + b"\x01b01\x02JA\x04"


def test_read_dots_picture_parses_the_write_command_the_sign_answers_with() -> None:
    # Table 24, p. 41: the Sign answers with "I", the File Label, and the picture data
    # laid out as in Table 22. These are Table 60's rows.
    rows = b"".join(row.encode("ascii") + b"\r" for row in TABLE_60_ROWS)

    picture = ReadDotsPicture("A").parse((ResponseItem("I", b"A0F09" + rows),))

    assert picture == DotsPicture.parse("\n".join(TABLE_60_ROWS))


def test_read_dots_picture_reads_rows_the_way_the_sign_does() -> None:
    # p. 40: LF after CR is optional, the last CR is optional, a short row is padded
    # with off pixels, a long one is cut at the Width, and the Sign clears the picture
    # after the Width, so rows never sent are off.
    data = b"B0403" + b"12\r\n" + b"3\r\n" + b"4567"

    picture = ReadDotsPicture("B").parse((ResponseItem("I", data),))

    assert picture == DotsPicture.parse("120\n300\n456\n000")


def test_read_dots_picture_refuses_an_answer_for_another_file() -> None:
    with pytest.raises(UnexpectedResponseError):
        ReadDotsPicture("A").parse((ResponseItem("I", b"B0101" + b"1\r"),))


@pytest.mark.parametrize("data", [b"AXX09", b"A0101" + b"9\r", b"A01"])
def test_read_dots_picture_refuses_malformed_data(data: bytes) -> None:
    with pytest.raises(ResponseError):
        ReadDotsPicture("A").parse((ResponseItem("I", data),))


# Validation against the Sign Model, and the Sign facade.

FULL_4120C = DotsPicture.parse("\n".join(["1" * 120] * 16))


def test_a_picture_the_size_of_the_4120cs_display_passes() -> None:
    # Table 5: the 4120C is 120 x 16 pixels.
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        validate(models.ALPHA_4120C, [WriteDotsPicture("A", FULL_4120C)], strict=True)


@pytest.mark.parametrize("text", ["\n".join(["1"] * 17), "1" * 121])
def test_a_picture_larger_than_the_display_is_reported(text: str) -> None:
    # Table 70, note 1: a graphic must fit the Sign's resolution (4120C: 120 x 16).
    command = WriteDotsPicture("A", DotsPicture.parse(text))

    with pytest.raises(UnsupportedCapability, match="120 x 16"):
        validate(models.ALPHA_4120C, [command], strict=True)
    with pytest.warns(UnsupportedCapabilityWarning, match="120 x 16"):
        validate(models.ALPHA_4120C, [command])


def test_a_model_without_the_graphic_capability_reports_pictures() -> None:
    capabilities = models.ALPHA_4120C.capabilities
    assert capabilities is not None
    no_graphic = replace(models.ALPHA_4120C, capabilities=capabilities - {Capability.GRAPHIC})
    write = WriteDotsPicture("A", DotsPicture.parse("1"))
    call = WriteText("B", Message(Frame(Mode.HOLD, content=[DotsPictureRef("A")])))

    for command in (write, call):
        with pytest.raises(UnsupportedCapability, match="graphic"):
            validate(no_graphic, [command], strict=True)


def test_red_models_report_pixels_other_than_red() -> None:
    # Table 69, note 1: models ending in R display red only.
    validate(models.ALPHA_4120R, [WriteDotsPicture("A", DotsPicture.parse("01"))], strict=True)

    with pytest.raises(UnsupportedCapability, match="color"):
        validate(models.ALPHA_4120R, [WriteDotsPicture("A", DotsPicture.parse("02"))], strict=True)


def test_the_generic_model_does_not_check_pictures() -> None:
    validate(models.GENERIC, [WriteDotsPicture("A", DotsPicture.parse("3" * 255))], strict=True)


def test_sign_writes_a_dots_picture_with_its_pause() -> None:
    transport = FakeTransport()
    sign = Sign(transport, model=models.ALPHA_4120C, checksum=False)

    sign.write_dots_picture("A", DotsPicture.parse("12\n30"))

    # Sign Type "a" (Table 5); Table 22's layout; the pause from p. 40.
    assert transport.events == [
        ("write", SYNC + b"\x01a00\x02IA0202"),
        ("pause", 0.1),
        ("write", b"12\r30\r\x04"),
    ]


def test_sign_reads_a_dots_picture_with_command_code_j() -> None:
    transport = FakeTransport()
    sign = Sign(transport, model=models.ALPHA_4120C, address=1, checksum=False)

    with pytest.raises(SignTimeoutError):
        sign.read_dots_picture("A")

    assert transport.written == SYNC + b"\x01a01\x02JA\x04"
