"""Finding Signs and their Sign Addresses with a Network Query (p. 32)."""

import pytest

from alpha_led_sign import discover, models
from alpha_led_sign.discovery import DiscoveredSign
from alpha_led_sign.protocol.commands import SerialErrorStatus
from tests.fakes import FakeTransport

SYNC = b"\x00" * 5
NULS = b"\x00" * 26
# Answers: "E-" + UAAZ (U = Sign Type, AA = Sign Address, Z = serial error status, p. 32).
# Captured from a 4120C (firmware 10184403 rev O (1206)) on 2026-11-15, at Sign Address
# 1 and then, after Set Sign Address, at 2.
FOUND_4120C_AT_01 = NULS + b"\x01000\x02E-a01@\x030179\x04"
FOUND_4120C_AT_02 = NULS + b"\x01000\x02E-a02@\x03017A\x04"


def test_network_query_is_broadcast_to_every_sign() -> None:
    transport = FakeTransport()

    discover(transport, checksum=False)

    # Read SPECIAL FUNCTION layout of Table 53 (p. 69), label "-" from p. 32.
    assert transport.written == SYNC + b"\x01Z00\x02F-\x04"


def test_discovered_signs_report_type_address_and_errors_sorted_by_address() -> None:
    transport = FakeTransport(
        responses=[FOUND_4120C_AT_02[:30], FOUND_4120C_AT_02[30:] + FOUND_4120C_AT_01]
    )

    found = discover(transport)

    assert found == [
        DiscoveredSign("a", 0x01, SerialErrorStatus()),
        DiscoveredSign("a", 0x02, SerialErrorStatus()),
    ]
    assert found[0].model is models.ALPHA_4120C


def test_discovery_waits_long_enough_for_the_highest_address_to_answer() -> None:
    # p. 32: a Sign answers after 1 s + 0.5 s x its address; allow 1 s more.
    transport = FakeTransport()

    discover(transport, max_address=15)

    assert transport.read_timeouts[0] == pytest.approx(1 + 15 * 0.5 + 1, abs=0.1)


def test_garbled_answers_are_skipped_with_a_warning() -> None:
    # p. 32: two Signs with one address collide and garble each other.
    garbled = NULS + b"\x01000\x02E-a01@\x030000\x04"  # checksum 0000 can't match this data
    transport = FakeTransport(responses=[garbled, FOUND_4120C_AT_02])

    with pytest.warns(UserWarning, match="garbled"):
        found = discover(transport)

    assert [sign.address for sign in found] == [0x02]
