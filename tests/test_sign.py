"""The Sign facade over FakeTransport: the Packets and pauses it sends."""

from datetime import datetime

import pytest

from alpha_led_sign import Sign, models
from alpha_led_sign.models import UnsupportedCapability, UnsupportedCapabilityWarning
from alpha_led_sign.protocol.codes import Color, Font, Mode, Position, StringRef
from alpha_led_sign.protocol.commands import TimeFormat, Tone
from alpha_led_sign.protocol.memory import StringFile, TextFile
from alpha_led_sign.protocol.message import Frame, Message
from tests.fakes import FakeTransport

SYNC = b"\x00" * 5


def test_show_writes_text_file_a_to_the_models_sign_type_with_a_checksum() -> None:
    transport = FakeTransport()
    sign = Sign(transport, model=models.ALPHA_4120C)

    sign.show("Hello")

    # HOLD in FILL position; checksum 02+41+41+1B+30+62+"Hello"(1F4)+03 = 0328.
    assert transport.written == SYNC + b"\x01a00\x02AA\x1b0bHello\x030328\x04"


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


def test_the_api_sketch_in_the_plan_runs() -> None:
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
