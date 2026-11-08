"""Finding Signs and their Sign Addresses with a Network Query (p. 32)."""

import pytest

from alpha_led_sign import discover, models
from alpha_led_sign.discovery import DiscoveredSign
from alpha_led_sign.protocol.commands import SerialErrorStatus
from tests.fakes import FakeTransport

SYNC = b"\x00" * 5
NULS = b"\x00" * 20
# Checksums by hand: STX + "E-" + UAAZ + ETX.
FOUND_4120C_AT_0F = NULS + b"\x01000\x02E-a0F@\x03018E\x04"  # 2+45+2D+61+30+46+40+3 = 18E
FOUND_4080C_AT_02 = NULS + b"\x01000\x02E-t02P\x03019D\x04"  # 2+45+2D+74+30+32+50+3 = 19D


def test_network_query_is_broadcast_to_every_sign() -> None:
    transport = FakeTransport()

    discover(transport)

    # 02+46+2D+03 = 78
    assert transport.written == SYNC + b"\x01Z00\x02F-\x030078\x04"


def test_discovered_signs_report_type_address_and_errors_sorted_by_address() -> None:
    transport = FakeTransport(
        responses=[FOUND_4120C_AT_0F[:30], FOUND_4120C_AT_0F[30:] + FOUND_4080C_AT_02]
    )

    found = discover(transport)

    assert found == [
        DiscoveredSign("t", 0x02, SerialErrorStatus(checksum_error=True)),
        DiscoveredSign("a", 0x0F, SerialErrorStatus()),
    ]
    assert found[1].model is models.ALPHA_4120C


def test_discovery_waits_long_enough_for_the_highest_address_to_answer() -> None:
    # p. 32: a Sign answers after 1 s + 0.5 s x its address; allow 1 s more.
    transport = FakeTransport()

    discover(transport, max_address=15)

    assert transport.read_timeouts[0] == pytest.approx(1 + 15 * 0.5 + 1, abs=0.1)


def test_garbled_answers_are_skipped_with_a_warning() -> None:
    # p. 32: two Signs with one address collide and garble each other.
    garbled = NULS + b"\x01000\x02E-a0F@\x030000\x04"
    transport = FakeTransport(responses=[garbled, FOUND_4080C_AT_02])

    with pytest.warns(UserWarning, match="garbled"):
        found = discover(transport)

    assert [sign.address for sign in found] == [0x02]
