"""Finding Signs and their Sign Addresses with a Network Query (p. 32)."""

import pytest

from alpha_led_sign import discover, models
from alpha_led_sign.discovery import DiscoveredSign
from alpha_led_sign.protocol.commands import SerialErrorStatus
from tests.fakes import FakeLine

SYNC = b"\x00" * 5
NULS = b"\x00" * 26
# Answers: "E-" + UAAZ (U = Sign Type, AA = Sign Address, Z = serial error status, p. 32).
# Captured from a 4120C (firmware 10184403 rev O (1206)) on 2026-11-15, at Sign Address
# 1 and then, after Set Sign Address, at 2.
FOUND_4120C_AT_01 = NULS + b"\x01000\x02E-a01@\x030179\x04"
FOUND_4120C_AT_02 = NULS + b"\x01000\x02E-a02@\x03017A\x04"


QUERY = b"F-"  # Read SPECIAL FUNCTION "-" (Table 53, p. 69; p. 32)


def test_network_query_is_broadcast_to_every_sign() -> None:
    line = FakeLine()

    discover(line, checksum=False, clock=line.clock)

    # Read SPECIAL FUNCTION layout of Table 53 (p. 69), label "-" from p. 32.
    assert line.written == SYNC + b"\x01Z00\x02F-\x04"


def test_discovered_signs_report_type_address_and_errors_sorted_by_address() -> None:
    line = FakeLine()
    line.answer(QUERY, FOUND_4120C_AT_02[:30], FOUND_4120C_AT_02[30:] + FOUND_4120C_AT_01)

    found = discover(line, clock=line.clock)

    assert found == [
        DiscoveredSign("a", 0x01, SerialErrorStatus()),
        DiscoveredSign("a", 0x02, SerialErrorStatus()),
    ]
    assert found[0].model is models.ALPHA_4120C


def test_discovery_waits_long_enough_for_the_highest_address_to_answer() -> None:
    # p. 32: a Sign answers after 1 s + 0.5 s x its address; allow 1 s more.
    line = FakeLine()

    discover(line, max_address=15, clock=line.clock)

    assert line.now == pytest.approx(1 + 15 * 0.5 + 1)


def test_discovery_keeps_reading_until_its_deadline() -> None:
    # p. 32: Sign Address 1 answers 1.5 s after the query. With max_address=1 the
    # deadline is 1 + 0.5 + 1 = 2.5 s, so an answer at 3 s is too late.
    line = FakeLine()
    line.answer(QUERY, FOUND_4120C_AT_01, delay=1.5)
    line.arrive(FOUND_4120C_AT_02, at=3.0)

    found = discover(line, max_address=1, clock=line.clock)

    assert [sign.address for sign in found] == [0x01]
    assert line.now == pytest.approx(2.5)


def test_garbled_answers_are_skipped_with_a_warning() -> None:
    # p. 32: two Signs with one address collide and garble each other.
    garbled = NULS + b"\x01000\x02E-a01@\x030000\x04"  # checksum 0000 can't match this data
    line = FakeLine()
    line.answer(QUERY, garbled, FOUND_4120C_AT_02)

    with pytest.warns(UserWarning, match="garbled"):
        found = discover(line, clock=line.clock)

    assert [sign.address for sign in found] == [0x02]
