"""Read Commands: the requests they send and the Responses they parse."""

from datetime import time

import pytest

from alpha_led_sign.protocol.codes import (
    Attribute,
    CharacterAttribute,
    CharacterFlash,
    Color,
    Control,
    CurrentDate,
    CurrentTime,
    DateFormat,
    DoubleHigh,
    Font,
    Mode,
    Position,
    RawControl,
    Spacing,
    SpecialGraphic,
    SpecialMode,
    Speed,
    StringRef,
    TrueDescenders,
    Wide,
)
from alpha_led_sign.protocol.commands import (
    GeneralInformation,
    ReadDayOfWeek,
    ReadGeneralInformation,
    ReadSerialErrorStatus,
    ReadString,
    ReadText,
    SerialErrorStatus,
    SoftReset,
    TimeFormat,
    Weekday,
    WriteString,
    WriteText,
)
from alpha_led_sign.protocol.message import Frame, Message
from alpha_led_sign.protocol.packet import Recipient, ResponseItem, decode_response, encode_packet
from alpha_led_sign.protocol.response import ResponseError, UnexpectedResponseError

SYNC = b"\x00" * 5
NULS = b"\x00" * 20


def test_read_text_request_matches_table_45() -> None:
    packet = encode_packet(Recipient("Z", 6), [ReadText("C")], checksum=False)

    assert bytes(packet) == SYNC + b"\x01Z06\x02BC\x04"


def test_read_text_parses_the_response_in_table_46() -> None:
    response = decode_response(NULS + b"\x01000\x02ACFILE C\x03020C\x04")

    # The file holds plain text with no Mode Field.
    assert ReadText("C").parse(response) == Message(Frame(None, content="FILE C"))


def test_a_message_reads_back_as_the_message_that_was_written() -> None:
    message = Message(
        Frame(
            SpecialMode.SNOW, Position.TOP, [Color.RED, Font.SEVEN_HIGH, "Temp: ", StringRef("T")]
        ),
        Frame(Mode.ROTATE, Position.TOP),
        Frame(SpecialGraphic.FIREWORKS, Position.FILL),
        Frame(
            Mode.HOLD,
            Position.BOTTOM,
            [
                Speed.SPEED_2,
                Wide(True),
                DoubleHigh(False),
                TrueDescenders(True),
                CharacterFlash(True),
                CharacterAttribute(Attribute.FANCY, True),
                Spacing.FIXED_WIDTH,
                CurrentTime(),
                Control.NEW_LINE,
                CurrentDate(DateFormat.DAY_OF_WEEK),
                Control.NEW_PAGE,
                Wide(False),
                "done",
            ],
        ),
    )
    written = WriteText("B", message).encode_data()

    assert ReadText("B").parse((ResponseItem("A", written),)) == message


def test_control_bytes_the_library_does_not_model_survive_a_round_trip() -> None:
    # 08H + "z" shows Counter 1 (Appendix G, p. 87).
    data = b"B\x1b0bDays: \x08z"

    message = ReadText("B").parse((ResponseItem("A", data),))

    assert message == Message(Frame(Mode.HOLD, Position.FILL, ["Days: ", RawControl(b"\x08z")]))
    assert WriteText("B", message).encode_data() == data


def test_only_the_first_frame_may_lack_a_mode() -> None:
    with pytest.raises(ValueError, match="first Frame"):
        Message(Frame(Mode.HOLD, content="a"), Frame(None, content="b"))


def test_a_read_must_be_the_last_command_in_a_packet() -> None:
    # p. 11: only one Read Command Code, and it must be last.
    with pytest.raises(ValueError, match="last"):
        encode_packet(Recipient("Z", 0), [ReadText("A"), SoftReset()])


def test_read_text_rejects_a_response_to_something_else() -> None:
    with pytest.raises(UnexpectedResponseError, match="TEXT File C"):
        ReadText("C").parse((ResponseItem("A", b"DFILE D"),))


def test_a_malformed_answer_is_not_mistaken_for_an_answer_to_something_else() -> None:
    with pytest.raises(ResponseError) as raised:
        ReadSerialErrorStatus().parse((ResponseItem("E", b"*@@"),))

    assert not isinstance(raised.value, UnexpectedResponseError)


def test_read_string_request_and_response_match_tables_58_and_59() -> None:
    packet = encode_packet(Recipient("f", 8), [ReadString("2")], checksum=False)
    response = decode_response(NULS + b"\x01000\x02G28,234,000\x030237\x04")

    assert bytes(packet) == SYNC + b"\x01f08\x02H2\x04"
    assert ReadString("2").parse(response) == ("8,234,000",)


def test_string_content_reads_back_as_written() -> None:
    content = (Color.AMBER, Spacing.FIXED_WIDTH, "72F", Control.NEW_LINE, CurrentTime())
    written = WriteString("T", content).encode_data()

    assert ReadString("T").parse((ResponseItem("G", written),)) == content


def test_read_day_of_week_matches_tables_53_and_54() -> None:
    packet = encode_packet(Recipient("Z", 4), [ReadDayOfWeek()], checksum=False)
    response = decode_response(NULS + b"\x01000\x02E&6\x0300A6\x04")

    assert bytes(packet) == SYNC + b"\x01Z04\x02F&\x04"
    assert ReadDayOfWeek().parse(response) == Weekday.FRIDAY


@pytest.mark.parametrize(
    ("register", "expected"),
    [
        (0x40, SerialErrorStatus()),
        (0x50, SerialErrorStatus(checksum_error=True)),
        (
            0x7F,
            SerialErrorStatus(
                illegal_command=True,
                checksum_error=True,
                buffer_overflow=True,
                timeout=True,
                framing_error=True,
                parity_error=True,
            ),
        ),
    ],
)
def test_serial_error_status_register_bits_follow_page_31(
    register: int, expected: SerialErrorStatus
) -> None:
    response = (ResponseItem("E", b"*" + bytes([register])),)

    assert (
        encode_packet(Recipient("Z", 1), [ReadSerialErrorStatus()])
        .chunks[0]
        .data.endswith(b"\x02F*\x030075\x04")
    )
    status = ReadSerialErrorStatus().parse(response)
    assert status == expected
    assert status.ok is (register == 0x40)


@pytest.mark.parametrize("leading_nul", [b"\x00", b""])
def test_general_information_fields_follow_page_29(leading_nul: bytes) -> None:
    # p. 29: [NUL] FFFFFFFF f MmYy HhNn R SS POOL,pool (the NUL is sent by some Signs only).
    data = b'"' + leading_nul + b"FIRMWARE" + b"B" + b"0193" + b"1430" + b"S" + b"FF" + b"6D60,5A00"

    info = ReadGeneralInformation().parse((ResponseItem("E", data),))

    assert info == GeneralInformation(
        firmware="FIRMWARE",
        revision="B",
        firmware_date="0193",
        time=time(14, 30),
        time_format=TimeFormat.AM_PM,
        speaker_enabled=False,
        memory_total=0x6D60,
        memory_free=0x5A00,
    )


def test_general_information_of_the_wrong_length_is_rejected() -> None:
    with pytest.raises(ValueError, match="General Information"):
        ReadGeneralInformation().parse((ResponseItem("E", b'"FIRMWARE'),))
