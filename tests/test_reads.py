"""Read Commands: the Packets they send and the Responses they parse."""

from datetime import time

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


def test_read_text_packet_matches_table_45() -> None:
    packet = encode_packet(Recipient("Z", 6), [ReadText("C")], checksum=False)

    assert bytes(packet) == SYNC + b"\x01Z06\x02BC\x04"


def test_read_text_parses_the_response_in_table_46() -> None:
    response = decode_response(NULS + b"\x01000\x02ACFILE C\x03020C\x04")

    # The file holds plain text with no Mode Field.
    assert ReadText("C").parse(response) == Message(Frame(None, content="FILE C"))


@pytest.mark.parametrize(
    ("data", "code"),
    [
        (b"\x1c1", Color.RED),  # Appendix G, p. 82
        (b"\x1c3", Color.AMBER),  # p. 82
        (b"\x1a3", Font.SEVEN_HIGH),  # p. 82
        (b"\x10T", StringRef("T")),  # p. 81
        (b"\x14A", DotsPictureRef("A")),  # p. 81
        (b"\x16", Speed.SPEED_2),  # p. 81
        (b"\x12", Wide(True)),  # p. 81
        (b"\x11", Wide(False)),  # p. 81
        (b"\x050", DoubleHigh(False)),  # p. 81
        (b"\x061", TrueDescenders(True)),  # p. 81
        (b"\x071", CharacterFlash(True)),  # p. 81
        (b"\x1d51", CharacterAttribute(Attribute.FANCY, True)),  # p. 82
        (b"\x1e1", Spacing.FIXED_WIDTH),  # p. 82
        (b"\x13", CurrentTime()),  # p. 81
        (b"\x0d", Control.NEW_LINE),  # p. 81
        (b"\x0b9", CurrentDate(DateFormat.DAY_OF_WEEK)),  # p. 81
        (b"\x0c", Control.NEW_PAGE),  # p. 81
    ],
)
def test_control_codes_decode_from_appendix_g_bytes(data: bytes, code: ControlCode) -> None:
    # ESC "0" "b": FILL and HOLD (Tables 12 and 47).
    message = ReadText("B").parse((ResponseItem("A", b"B\x1b0b" + data),))

    assert message == Message(Frame(Mode.HOLD, Position.FILL, [code]))


def test_mode_fields_decode_from_tables_47_48_and_67() -> None:
    # Table 47 (p. 65): ROTATE on the bottom line.
    assert ReadText("D").parse((ResponseItem("A", b"D\x1b&aHELLO"),)) == Message(
        Frame(Mode.ROTATE, Position.BOTTOM, "HELLO")
    )
    # Table 48 (pp. 65-66): SNOW on the top line, then a ROTATE Frame with no text.
    assert ReadText(">").parse((ResponseItem("A", b'>\x1b"n2Hello There\x1b"a'),)) == Message(
        Frame(SpecialMode.SNOW, Position.TOP, "Hello There"), Frame(Mode.ROTATE, Position.TOP)
    )
    # Table 67 (p. 90): FIREWORKS is Special Graphic "X", shown here in the FILL Display Position.
    assert ReadText("B").parse((ResponseItem("A", b"B\x1b0nX"),)) == Message(
        Frame(SpecialGraphic.FIREWORKS, Position.FILL)
    )


def test_string_content_decodes_from_appendix_g_bytes() -> None:
    # Amber (1CH "3"), fixed width (1EH "1"), new line (0DH), time (13H): Appendix G, pp. 81-82.
    response = (ResponseItem("G", b"T\x1c3\x1e172F\x0d\x13"),)

    assert ReadString("T").parse(response) == (
        Color.AMBER,
        Spacing.FIXED_WIDTH,
        "72F",
        Control.NEW_LINE,
        CurrentTime(),
    )


def test_a_message_round_trip_gives_back_the_message_that_was_written() -> None:
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


def test_read_string_packet_and_response_match_tables_58_and_59() -> None:
    packet = encode_packet(Recipient("f", 8), [ReadString("2")], checksum=False)
    response = decode_response(NULS + b"\x01000\x02G28,234,000\x030237\x04")

    assert bytes(packet) == SYNC + b"\x01f08\x02H2\x04"
    assert ReadString("2").parse(response) == ("8,234,000",)


def test_a_string_content_round_trip_gives_back_what_was_written() -> None:
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

    # Read SPECIAL FUNCTION layout of Table 53 (p. 69), label "*" from p. 31.
    packet = encode_packet(Recipient("Z", 1), [ReadSerialErrorStatus()], checksum=False)
    assert bytes(packet).endswith(b"\x02F*\x04")
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
