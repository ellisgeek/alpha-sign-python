"""SPECIAL FUNCTION Commands ("E"), checked against Table 15 and Appendix F."""

from datetime import date, time

import pytest

from alpha_led_sign.protocol.commands import (
    Beep,
    ClearMemory,
    ClearSerialErrorStatus,
    ProgrammableTone,
    RunDay,
    RunDays,
    RunOrder,
    SetDate,
    SetDayOfWeek,
    SetMemoryConfiguration,
    SetRunDays,
    SetRunSequence,
    SetRunTimes,
    SetSerialAddress,
    SetSpeaker,
    SetTime,
    SetTimeFormat,
    SoftReset,
    TimeFormat,
    Tone,
    Weekday,
    WriteText,
)
from alpha_led_sign.protocol.memory import DotsPictureFile, RunTime, StringFile, TextFile
from alpha_led_sign.protocol.message import Message
from alpha_led_sign.protocol.packet import Chunk, Recipient, encode_packet

SYNC = b"\x00" * 5
ALL_SIGNS = Recipient("Z", 0)


def test_set_time_of_day_matches_table_52() -> None:
    packet = encode_packet(ALL_SIGNS, [SetTime(time(14, 30))], checksum=False)

    assert bytes(packet) == SYNC + b"\x01Z00\x02E 1430\x04"


def test_set_time_format_nested_with_a_text_write_matches_table_42() -> None:
    hello = WriteText("A", Message())
    commands = [SetTimeFormat(TimeFormat.AM_PM), hello]

    packet = encode_packet(ALL_SIGNS, commands)

    assert bytes(packet).startswith(SYNC + b"\x01Z00\x02E'S\x0300C4\x02")


def test_set_memory_configuration_matches_table_55() -> None:
    files = [
        TextFile("A", size=256),
        DotsPictureFile("m", rows=7, columns=60),
        StringFile("l", size=10),
    ]

    packet = encode_packet(ALL_SIGNS, [SetMemoryConfiguration(files)], checksum=False)

    # Table 55's packet line prints the letter O in "mDUO73C"; its item I gives "073C".
    assert bytes(packet) == SYNC + b"\x01Z00\x02E$AAU0100FF00mDU073C1000lBL000A0000\x04"


def test_clear_memory_is_the_memory_configuration_label_alone() -> None:
    # p. 21: "To Clear Memory just use 'E$'."
    packet = encode_packet(ALL_SIGNS, [ClearMemory()], checksum=False)

    assert bytes(packet) == SYNC + b"\x01Z00\x02E$\x04"


def test_memory_configuration_needs_at_least_one_file() -> None:
    with pytest.raises(ValueError, match="ClearMemory"):
        SetMemoryConfiguration([])


@pytest.mark.parametrize("size", [-1, 0x10000])
def test_file_sizes_fit_four_hex_digits(size: int) -> None:
    with pytest.raises(ValueError, match="size"):
        TextFile("A", size=size)


@pytest.mark.parametrize(
    ("start", "expected"),
    [(time(0, 0), "00"), (time(8, 50), "35"), (time(16, 0), "60"), (time(23, 50), "8F")],
)
def test_run_time_codes_match_appendix_b(start: time, expected: str) -> None:
    assert RunTime.between(start, time(0, 0)).encode() == f"{expected}00".encode()


def test_run_times_are_in_ten_minute_steps() -> None:
    with pytest.raises(ValueError, match="10-minute"):
        RunTime.between(time(8, 5), time(9, 0))


def test_set_run_times_sends_label_start_and_stop_for_each_text_file() -> None:
    # Table 15, ")" (p. 22): FQQQQ for each TEXT File. Appendix B: 8:00 a.m. = 30H, 5:00 p.m. = 66H.
    command = SetRunTimes({"A": RunTime.between(time(8, 0), time(17, 0)), "B": RunTime.NEVER})

    assert command.encode_data() == b")A3066BFE00"


def test_set_date_is_month_day_two_digit_year() -> None:
    # Table 15, ";" (p. 26): mmddyy.
    assert SetDate(date(2026, 11, 7)).encode_data() == b";110726"


def test_set_date_rejects_years_the_two_digit_window_cannot_hold() -> None:
    # p. 28, note 15: "00"-"96" = 2000-2096 and "97"-"99" = 1997-1999.
    with pytest.raises(ValueError, match="1997"):
        SetDate(date(2097, 1, 1))


def test_set_day_of_week_counts_from_sunday() -> None:
    # Table 15, "&" (p. 22): "1" = Sunday ... "7" = Saturday. 2026-11-07 is a Saturday.
    assert SetDayOfWeek(Weekday.SUNDAY).encode_data() == b"&1"
    assert SetDayOfWeek(Weekday.of(date(2026, 11, 7))).encode_data() == b"&7"


def test_set_run_sequence_is_order_lock_then_labels() -> None:
    # Table 15, "." (p. 23): KPF..., "T" = by Run Time, "S" = in order, "U"/"L" = lock.
    assert SetRunSequence("ABC").encode_data() == b".TUABC"
    assert SetRunSequence(["A", "B"], order=RunOrder.IN_ORDER, locked=True).encode_data() == (
        b".SLAB"
    )


@pytest.mark.parametrize("labels", ["", "A" * 129])
def test_run_sequence_holds_1_to_128_files(labels: str) -> None:
    with pytest.raises(ValueError, match="1 to 128"):
        SetRunSequence(labels)


def test_set_run_days_sends_label_start_and_stop_day_for_each_file() -> None:
    # Table 15, "2" (p. 24): FSs. "8" = Monday-Friday, "2" = Monday ... "6" = Friday.
    command = SetRunDays(
        {
            "A": RunDays(RunDay.WEEKDAYS),
            "B": RunDays(RunDay.MONDAY, stop=Weekday.FRIDAY),
        }
    )

    assert command.encode_data() == b"2A81B26"


def test_speaker_enable_and_disable_match_table_15() -> None:
    # "!" (p. 21): "00" = enable, "FF" = disable.
    assert SetSpeaker(True).encode_data() == b"!00"
    assert SetSpeaker(False).encode_data() == b"!FF"


def test_fixed_tones_end_the_packet_with_three_seconds_of_silence() -> None:
    # "(" (p. 22): "0" = 2 s tone, "1" = three short beeps. p. 27 note 4: wait 3 s.
    packet = encode_packet(ALL_SIGNS, [Beep(Tone.THREE_BEEPS)], checksum=False)

    assert packet.chunks == (Chunk(SYNC + b"\x01Z00\x02E(1\x04", pause_after=3.0),)
    assert Beep(Tone.CONTINUOUS).encode_data() == b"(0"


def test_programmable_tone_is_frequency_duration_repeats_in_hex() -> None:
    # "(" (p. 22): "2" + FFDR, D in 0.1 s steps.
    tone = ProgrammableTone(frequency=0xA0, duration=5, repeats=3)

    assert tone.encode_data() == b"(2A053"
    # p. 27 note 5: wait until it has finished: 4 plays of 0.5 s.
    assert tone.pause_after == pytest.approx(2.0)


@pytest.mark.parametrize(
    ("frequency", "duration", "repeats"), [(0xFF, 1, 0), (0, 0, 0), (0, 0x10, 0), (0, 1, 0x10)]
)
def test_programmable_tone_values_fit_their_fields(
    frequency: int, duration: int, repeats: int
) -> None:
    with pytest.raises(ValueError, match="tone"):
        ProgrammableTone(frequency=frequency, duration=duration, repeats=repeats)


def test_a_tone_must_be_the_last_command() -> None:
    # p. 27 note 2: the serial port is disabled while a tone plays.
    with pytest.raises(ValueError, match="last"):
        encode_packet(ALL_SIGNS, [Beep(Tone.CONTINUOUS), ClearMemory()])


def test_soft_reset_and_clear_serial_error_status_have_no_data() -> None:
    # Table 15 (p. 22, p. 24): "," = Soft Reset, "4" = Clear Serial Error Status Register.
    assert SoftReset().encode_data() == b","
    assert ClearSerialErrorStatus().encode_data() == b"4"


def test_set_serial_address_is_two_hex_digits() -> None:
    # Table 15, "7" (p. 26).
    assert SetSerialAddress(0x2F).encode_data() == b"72F"
    with pytest.raises(ValueError, match="0-255"):
        SetSerialAddress(256)
