"""The Sign facade over FakeTransport: the Packets and pauses it sends."""

from datetime import datetime, time

import pytest

from alpha_led_sign import (
    RunDay,
    RunDays,
    RunOrder,
    RunTime,
    Sign,
    SignTimeoutError,
    Weekday,
    models,
)
from alpha_led_sign.markup import MarkupError
from alpha_led_sign.models import UnsupportedCapability, UnsupportedCapabilityWarning
from alpha_led_sign.protocol.codes import Color, Font, Mode, Position, StringRef
from alpha_led_sign.protocol.commands import ReadDayOfWeek, TimeFormat, Tone
from alpha_led_sign.protocol.memory import StringFile, TextFile
from alpha_led_sign.protocol.message import Frame, Message
from alpha_led_sign.protocol.response import ResponseError, UnexpectedResponseError
from tests.fakes import FakeTransport
from tests.vectors import TABLE_41

SYNC = b"\x00" * 5


def test_a_checksummed_write_to_every_sign_matches_table_41() -> None:
    transport = FakeTransport()
    sign = Sign(transport)  # the generic model: Sign Type Z, address 00

    sign.write_text("A", Message(Frame(None, content="HELLO")))

    assert transport.written == TABLE_41


def test_show_writes_text_file_a_to_the_models_sign_type_with_a_mode_field() -> None:
    transport = FakeTransport()
    sign = Sign(transport, model=models.ALPHA_4120C, checksum=False)

    sign.show("Hello")

    # Sign Type "a" (Table 5); Mode Field ESC, FILL "0", HOLD "b" (Tables 12 and 47).
    assert transport.written == SYNC + b"\x01a00\x02AA\x1b0bHello\x04"


def test_set_clock_nests_time_date_and_weekday_with_pauses_after_each_stx() -> None:
    transport = FakeTransport()
    sign = Sign(transport, model=models.ALPHA_4120C, checksum=False)

    sign.set_clock(datetime(2026, 11, 7, 14, 30, 59))  # a Saturday

    assert transport.events == [
        ("write", SYNC + b"\x01a00\x02"),
        ("pause", 0.1),
        ("write", b"E 1430\x03\x02"),
        ("pause", 0.1),
        ("write", b"E;110726\x03\x02"),
        ("pause", 0.1),
        ("write", b"E&7\x03\x04"),
    ]


def test_beep_is_followed_by_three_seconds_of_silence() -> None:
    transport = FakeTransport()

    Sign(transport).beep(Tone.THREE_BEEPS)

    assert transport.events[-1] == ("pause", 3.0)


def test_strict_sign_refuses_unsupported_content_before_sending_anything() -> None:
    transport = FakeTransport()
    sign = Sign(transport, model=models.ALPHA_4120C, strict=True)

    with pytest.raises(UnsupportedCapability):
        sign.show("squeezed", mode=Mode.COMPRESSED_ROTATE)

    assert transport.events == []


def test_advisory_sign_warns_and_sends_anyway() -> None:
    transport = FakeTransport()
    sign = Sign(transport, model=models.ALPHA_4120C)

    with pytest.warns(UnsupportedCapabilityWarning):
        sign.show("squeezed", mode=Mode.COMPRESSED_ROTATE)

    assert b"\x1b0tsqueezed" in transport.written


def unchecked_sign() -> tuple[Sign, FakeTransport]:
    """A GENERIC Sign (Sign Type Z, address 0) without checksums, to match Appendix F."""
    transport = FakeTransport()
    return Sign(transport, checksum=False), transport


def test_priority_and_clear_priority_match_tables_50_and_51() -> None:
    sign, transport = unchecked_sign()

    sign.priority(Frame(Mode.FLASH, Position.MIDDLE, [Font.FULL_HEIGHT, "EMERGENCY"]))
    sign.clear_priority()

    assert transport.written == (
        SYNC + b"\x01Z00\x02A0\x1b c\x1a9EMERGENCY\x04" + SYNC + b"\x01Z00\x02A0\x04"
    )


def test_write_text_takes_a_message_a_frame_or_plain_text() -> None:
    sign, transport = unchecked_sign()
    frame = Frame(Mode.ROTATE, Position.TOP, [Color.RED, "Temp: ", StringRef("T")])

    sign.write_text("B", Message(frame, Frame(Mode.HOLD)))
    sign.write_text("C", frame)
    sign.write_text("D", "plain")

    assert transport.written == (
        SYNC
        + b'\x01Z00\x02AB\x1b"a\x1c1Temp: \x10T\x1b0b\x04'
        + SYNC
        + b'\x01Z00\x02AC\x1b"a\x1c1Temp: \x10T\x04'
        + SYNC
        + b"\x01Z00\x02AD\x1b0bplain\x04"
    )


def test_write_string_matches_table_57() -> None:
    sign, transport = unchecked_sign()

    sign.write_string("1", "7,345")

    assert transport.written == SYNC + b"\x01Z00\x02G17,345\x04"


def test_memory_and_housekeeping_commands() -> None:
    sign, transport = unchecked_sign()

    sign.configure_memory([TextFile("A", size=256), StringFile("l", size=10)])
    sign.clear_memory()
    sign.soft_reset()
    sign.set_time_format(TimeFormat.TWENTY_FOUR_HOUR)
    sign.run_sequence("AB")

    packets = transport.written.split(SYNC)[1:]
    assert packets == [
        b"\x01Z00\x02E$AAU0100FF00lBL000A0000\x04",
        b"\x01Z00\x02E$\x04",
        b"\x01Z00\x02E,\x04",
        b"\x01Z00\x02E'M\x04",
        b"\x01Z00\x02E.TUAB\x04",
    ]


def test_sign_closes_its_transport_when_used_as_a_context_manager() -> None:
    transport = FakeTransport()

    with Sign(transport) as sign:
        sign.show("hi")

    assert transport.closed


def test_the_readme_example_runs() -> None:
    from alpha_led_sign import (
        Color,
        CurrentTime,
        Frame,
        Message,
        Mode,
        Position,
        StringFile,
        StringRef,
        TextFile,
    )

    transport = FakeTransport()
    with Sign(transport, model=models.ALPHA_4120C) as sign:
        sign.show("Hello")
        sign.configure_memory([TextFile("A", size=512), StringFile("T", size=16)])
        sign.write_text(
            "A",
            Message(
                Frame(Mode.ROTATE, Position.TOP, [Color.RED, "Temp: ", StringRef("T")]),
                Frame(Mode.HOLD, Position.BOTTOM, [Color.GREEN, CurrentTime()]),
            ),
        )
        sign.write_string("T", "72F")
        sign.set_clock(datetime(2026, 11, 7, 9, 41))
        sign.priority(Frame(Mode.FLASH, content=["EMERGENCY"]))
        sign.clear_priority()

    assert transport.written.count(SYNC) == 7


NULS = b"\x00" * 20


def test_read_text_sends_the_read_then_parses_the_response() -> None:
    transport = FakeTransport(responses=[NULS + b"\x01000\x02ACFI", b"LE C\x03020C\x04"])
    sign = Sign(transport, address=6, checksum=False)

    message = sign.read_text("C")

    assert transport.written == SYNC + b"\x01Z06\x02BC\x04"  # Table 45
    assert message == Message(Frame(None, content="FILE C"))  # Table 46


def test_read_string_and_serial_errors() -> None:
    transport = FakeTransport(
        responses=[
            NULS + b"\x01000\x02G28,234,000\x030237\x04",  # Table 59
            # Captured from a 4120C (firmware 10184403 rev O (1206)) on 2026-11-15.
            # Register 40H means no errors (p. 31).
            b"\x00" * 26 + b"\x01000\x02E*@\x0300B4\x04",
        ]
    )
    sign = Sign(transport, broadcast_reads=True)

    assert sign.read_string("2") == ("8,234,000",)
    assert sign.serial_errors().ok


def test_a_sign_that_does_not_answer_raises_sign_timeout() -> None:
    transport = FakeTransport(responses=[NULS + b"\x01000\x02ACFI"])

    with pytest.raises(SignTimeoutError):
        Sign(transport, broadcast_reads=True).read_text("C")


TABLE_46 = NULS + b"\x01000\x02ACFILE C\x03020C\x04"  # Read TEXT "C"
TABLE_54 = NULS + b"\x01000\x02E&6\x0300A6\x04"  # Read day of week
TABLE_59 = NULS + b"\x01000\x02G28,234,000\x030237\x04"  # Read STRING "2"


def test_a_late_answer_to_an_earlier_read_is_skipped() -> None:
    transport = FakeTransport()
    sign = Sign(transport, broadcast_reads=True)
    with pytest.raises(SignTimeoutError):
        sign.read_string("2")

    transport.responses = [TABLE_59, TABLE_46]

    assert sign.read_text("C") == Message(Frame(None, content="FILE C"))


def test_an_answer_already_waiting_is_discarded_before_a_read_is_sent() -> None:
    garbled = NULS + b"\x01000\x02ACFILE C\x03020D\x04"  # Table 46 with a bad checksum
    transport = FakeTransport(waiting=[garbled], responses=[TABLE_46])

    assert Sign(transport, broadcast_reads=True).read_text("C") == Message(
        Frame(None, content="FILE C")
    )


def test_the_rest_of_a_response_that_began_before_a_read_is_skipped() -> None:
    transport = FakeTransport(responses=[TABLE_54 + TABLE_59[:26]])
    sign = Sign(transport, broadcast_reads=True)
    assert sign.query(ReadDayOfWeek()) == Weekday.FRIDAY

    transport.responses = [TABLE_59[26:], TABLE_46]

    assert sign.read_text("C") == Message(Frame(None, content="FILE C"))


def test_a_response_to_another_read_raises_when_no_other_read_is_waiting() -> None:
    transport = FakeTransport(responses=[TABLE_59, TABLE_46])

    with pytest.raises(UnexpectedResponseError):
        Sign(transport, broadcast_reads=True).read_text("C")


def test_only_as_many_responses_are_skipped_as_reads_went_unanswered() -> None:
    transport = FakeTransport()
    sign = Sign(transport, broadcast_reads=True)
    with pytest.raises(SignTimeoutError):
        sign.read_string("2")

    transport.responses = [TABLE_59, TABLE_59, TABLE_46]

    with pytest.raises(UnexpectedResponseError):
        sign.read_text("C")


def test_a_garbled_answer_raises_instead_of_being_skipped() -> None:
    bad_checksum = NULS + b"\x01000\x02ACFILE C\x03020D\x04"
    transport = FakeTransport(responses=[bad_checksum])

    with pytest.raises(ResponseError, match="checksum"):
        Sign(transport, broadcast_reads=True).read_text("C")


def _checksumless_4120c(address: int | str = 1) -> tuple[Sign, FakeTransport]:
    """A 4120C at ``address`` that sends without checksums."""
    transport = FakeTransport()
    return Sign(transport, model=models.ALPHA_4120C, address=address, checksum=False), transport


def test_set_run_times_sends_each_text_files_start_and_stop() -> None:
    # Table 15, ")" (p. 22): FQQQQ per File. Appendix B: 8:00 a.m. = 30H, 5:00 p.m. = 66H,
    # Never = FEH. Table 38 layout: a lone Command without a Checksum has no ETX.
    sign, transport = _checksumless_4120c()

    sign.set_run_times({"A": RunTime.between(time(8, 0), time(17, 0)), "B": RunTime.NEVER})

    assert transport.events == [("write", SYNC + b"\x01a01\x02E)A3066BFE00\x04")]


def test_set_run_days_sends_each_text_files_start_and_stop_day() -> None:
    # Table 15, "2" (p. 24): FSs. "8" = Monday-Friday; "2" = Monday ... "6" = Friday.
    sign, transport = _checksumless_4120c()

    sign.set_run_days(
        {"A": RunDays(RunDay.WEEKDAYS), "B": RunDays(RunDay.MONDAY, stop=Weekday.FRIDAY)}
    )

    assert transport.events == [("write", SYNC + b"\x01a01\x02E2A81B26\x04")]


def test_run_sequence_takes_an_order_and_a_lock() -> None:
    # Table 15, "." (p. 23): KPF..., "T" = by Run Time, "S" = in order, "U"/"L" = lock.
    sign, transport = _checksumless_4120c()

    sign.run_sequence("AB")
    sign.run_sequence("AB", order=RunOrder.IN_ORDER, locked=True)

    assert transport.written == (SYNC + b"\x01a01\x02E.TUAB\x04" + SYNC + b"\x01a01\x02E.SLAB\x04")


def test_set_speaker_enables_and_disables() -> None:
    # Table 15, "!" (p. 21): "00" = enable, "FF" = disable.
    sign, transport = _checksumless_4120c()

    sign.set_speaker(True)
    sign.set_speaker(False)

    assert transport.written == SYNC + b"\x01a01\x02E!00\x04" + SYNC + b"\x01a01\x02E!FF\x04"


def test_tone_waits_until_every_play_has_finished() -> None:
    # Table 15, "(" (p. 22): "2" + FFDR, D in 0.1 s steps. p. 27, note 5: wait for the
    # tone to finish, here the first play and 3 repeats of 0.5 s each.
    sign, transport = _checksumless_4120c()

    sign.tone(0xA0, 5, repeats=3)

    assert transport.events == [
        ("write", SYNC + b"\x01a01\x02E(2A053\x04"),
        ("pause", pytest.approx(2.0)),
    ]


def test_set_sign_address_sends_the_new_address_and_then_uses_it() -> None:
    # Table 15, "7" (p. 26): two hex digits.
    sign, transport = _checksumless_4120c()

    sign.set_sign_address(0x2F)
    sign.set_speaker(True)

    assert transport.written == SYNC + b"\x01a01\x02E72F\x04" + SYNC + b"\x01a2F\x02E!00\x04"


@pytest.mark.parametrize("address", [0, "1?", "??"])
def test_set_sign_address_refuses_a_recipient_that_reaches_several_signs(
    address: int | str,
) -> None:
    sign, transport = _checksumless_4120c(address)

    with pytest.raises(ValueError, match="broadcast=True"):
        sign.set_sign_address(0x2F)

    assert transport.events == []


def test_set_sign_address_reaches_every_sign_when_asked() -> None:
    sign, transport = _checksumless_4120c(0)

    sign.set_sign_address(0x2F, broadcast=True)

    # Table 15, "7" (p. 26), sent to Sign Address 00, which every Sign hears (p. 11).
    assert transport.written == SYNC + b"\x01a00\x02E72F\x04"
    assert sign.recipient.address == 0x2F


@pytest.mark.parametrize("address", [0, "1?", "??"])
def test_a_read_to_a_recipient_that_reaches_several_signs_is_refused(
    address: int | str,
) -> None:
    # Every matching Sign answers a read, and their answers collide on the line.
    sign, transport = _checksumless_4120c(address)

    with pytest.raises(ValueError, match="broadcast_reads=True"):
        sign.read_text("C")

    assert transport.events == []


def test_a_read_to_a_recipient_that_reaches_several_signs_is_sent_when_asked() -> None:
    transport = FakeTransport(responses=[TABLE_46])
    sign = Sign(transport, checksum=False, broadcast_reads=True)

    message = sign.read_text("C")

    # Table 45, sent to Sign Address 00.
    assert transport.written == SYNC + b"\x01Z00\x02BC\x04"
    assert message == Message(Frame(None, content="FILE C"))  # Table 46


# Markup: Sign methods read a str as markup (.scratch/markup/spec.md).


def test_show_reads_markup() -> None:
    transport = FakeTransport()
    sign = Sign(transport, model=models.ALPHA_4120C, checksum=False)

    sign.show("{color red}Hi {{x}}")

    # Mode Field ESC "0" "b" (Tables 12, 47); 1CH "1" red (Appendix G, p. 82).
    assert transport.written == SYNC + b"\x01a00\x02AA\x1b0b\x1c1Hi {x}\x04"


def test_show_uses_its_mode_until_the_first_frame_token() -> None:
    transport = FakeTransport()
    sign = Sign(transport, model=models.ALPHA_4120C, checksum=False)

    sign.show("A{frame hold bottom}B", mode=Mode.ROTATE, position=Position.TOP)

    # Table 12: '"' top, "&" bottom; Table 65: "a" ROTATE, "b" HOLD.
    assert transport.written == SYNC + b'\x01a00\x02AA\x1b"aA\x1b&bB\x04'


def test_a_str_inside_a_segment_list_stays_literal() -> None:
    transport = FakeTransport()
    sign = Sign(transport, model=models.ALPHA_4120C, checksum=False)

    sign.show(["{color red}"])

    assert transport.written == SYNC + b"\x01a00\x02AA\x1b0b{color red}\x04"


def test_write_text_and_priority_read_markup() -> None:
    transport = FakeTransport()
    sign = Sign(transport, model=models.ALPHA_4120C, checksum=False)

    sign.write_text("B", "{frame}{time}")
    sign.priority("{frame flash}!")

    # 13H Call Time (p. 81); Priority TEXT File "0" (p. 20), FLASH "c" (Table 65).
    assert transport.written == (
        SYNC + b"\x01a00\x02AB\x13\x04" + SYNC + b"\x01a00\x02A0\x1b0c!\x04"
    )


def test_write_string_reads_markup_but_refuses_frames() -> None:
    transport = FakeTransport()
    sign = Sign(transport, model=models.ALPHA_4120C, checksum=False)

    sign.write_string("T", "{color amber}72")
    with pytest.raises(MarkupError):
        sign.write_string("T", "{frame hold}72")

    # Table 57 layout (p. 74); 1CH "3" amber (p. 82). Nothing sent for the refusal.
    assert transport.written == SYNC + b"\x01a00\x02GT\x1c372\x04"
