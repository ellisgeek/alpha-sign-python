"""Packet framing, checked against the worked examples in Appendix F of the manual."""

from dataclasses import dataclass
from typing import ClassVar

import pytest

from alpha_led_sign.protocol.commands import Command, Pause
from alpha_led_sign.protocol.packet import Chunk, Recipient, encode_packet

SYNC = b"\x00" * 5


@dataclass(frozen=True)
class Raw(Command):
    """A Command with literal bytes, so framing tests don't depend on content encoding."""

    code: ClassVar[str] = "A"
    data: bytes

    def encode_data(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class RawSpecial(Raw):
    code: ClassVar[str] = "E"


@dataclass(frozen=True)
class Paused(Command):
    """A Command whose data has silences in it, written where they fall."""

    code: ClassVar[str] = "A"

    def encode_data(self) -> tuple[bytes | Pause, ...]:
        return (b"AHE", Pause(0.1), b"LL", Pause(0.25), b"O")


SET_TIME_FORMAT_AM_PM = RawSpecial(b"'S")
WRITE_HELLO = Raw(b"AHELLO")


def test_single_command_without_checksum_matches_table_38() -> None:
    packet = encode_packet(Recipient("Z", 0), [Raw(b"AHELLO")], checksum=False)

    assert bytes(packet) == SYNC + b"\x01Z00\x02AAHELLO\x04"


def test_single_command_with_checksum_matches_table_41() -> None:
    packet = encode_packet(Recipient("Z", 0), [Raw(b"AHELLO")])

    assert bytes(packet) == SYNC + b"\x01Z00\x02AAHELLO\x0301FB\x04"


def test_nested_commands_with_checksums_match_table_42() -> None:
    packet = encode_packet(Recipient("Z", 0), [SET_TIME_FORMAT_AM_PM, WRITE_HELLO])

    assert bytes(packet) == SYNC + b"\x01Z00\x02E'S\x0300C4\x02AAHELLO\x0301FB\x04"


def test_nested_commands_without_checksums_match_table_43() -> None:
    packet = encode_packet(Recipient("Z", 0), [SET_TIME_FORMAT_AM_PM, WRITE_HELLO], checksum=False)

    assert bytes(packet) == SYNC + b"\x01Z00\x02E'S\x03\x02AAHELLO\x03\x04"


def test_wildcard_address_matches_table_40() -> None:
    packet = encode_packet(Recipient("l", "1?"), [WRITE_HELLO], checksum=False)

    assert bytes(packet) == SYNC + b"\x01l1?\x02AAHELLO\x04"


def test_multiple_recipients_match_table_44() -> None:
    recipients = [Recipient("a", 0x01), Recipient("r", "1?"), Recipient("U", 0x26)]

    packet = encode_packet(recipients, [WRITE_HELLO], checksum=False)

    assert bytes(packet) == SYNC + b"\x01a01,r1?,U26\x02AAHELLO\x04"


def test_single_command_is_sent_in_one_chunk_with_no_pause() -> None:
    packet = encode_packet(Recipient("Z", 0), [WRITE_HELLO])

    assert packet.chunks == (Chunk(SYNC + b"\x01Z00\x02AAHELLO\x0301FB\x04"),)


def test_nested_commands_pause_100ms_after_each_stx() -> None:
    packet = encode_packet(Recipient("Z", 0), [SET_TIME_FORMAT_AM_PM, WRITE_HELLO])

    assert packet.chunks == (
        Chunk(SYNC + b"\x01Z00\x02", pause_after=0.1),
        Chunk(b"E'S\x0300C4\x02", pause_after=0.1),
        Chunk(b"AAHELLO\x0301FB\x04"),
    )


@dataclass(frozen=True)
class RawTone(RawSpecial):
    """Stands in for a speaker tone, which needs 3 s of silence after it (p. 27, note 4)."""

    must_be_last: ClassVar[bool] = True

    @property
    def pause_after(self) -> float:
        return 3.0


def test_command_pause_follows_the_end_of_the_packet() -> None:
    packet = encode_packet(Recipient("Z", 0), [RawTone(b"(2")], checksum=False)

    assert packet.chunks == (Chunk(SYNC + b"\x01Z00\x02E(2\x04", pause_after=3.0),)


def test_a_command_that_must_be_last_cannot_be_followed_by_another() -> None:
    with pytest.raises(ValueError, match="must be the last"):
        encode_packet(Recipient("Z", 0), [RawTone(b"(2"), WRITE_HELLO])


def test_a_packet_needs_at_least_one_command() -> None:
    with pytest.raises(ValueError, match="at least one Command"):
        encode_packet(Recipient("Z", 0), [])


@pytest.mark.parametrize("byte", [b"\x01", b"\x02", b"\x03", b"\x04"])
def test_data_cannot_contain_framing_bytes(byte: bytes) -> None:
    with pytest.raises(ValueError, match="framing byte"):
        encode_packet(Recipient("Z", 0), [Raw(b"AHEL" + byte + b"LO")])


@pytest.mark.parametrize(
    ("sign_type", "address"),
    [("", 0), ("ab", 0), ("Z", -1), ("Z", 256), ("Z", "1"), ("Z", "1G"), ("Z", "100")],
)
def test_recipient_rejects_invalid_sign_type_or_address(sign_type: str, address: int | str) -> None:
    with pytest.raises(ValueError, match=r"Sign Type|Sign Address"):
        Recipient(sign_type, address)


@pytest.mark.parametrize(
    ("address", "several"),
    [(0, True), ("??", True), ("1?", True), ("?F", True), (1, False), (0x2F, False), ("2F", False)],
)
def test_broadcast_and_wildcard_recipients_reach_several_signs(
    address: int | str, several: bool
) -> None:
    # p. 11: address 00 reaches every Sign of the Sign Type, and "?" matches any digit.
    assert Recipient("Z", address).reaches_several is several


def test_a_pause_inside_a_commands_data_splits_the_packet_where_it_falls() -> None:
    packet = encode_packet(Recipient("Z", 0), [Paused()], checksum=True)

    # The bytes and Checksum are Table 41's: the pauses change only when they are sent.
    assert bytes(packet) == SYNC + b"\x01Z00\x02AAHELLO\x0301FB\x04"
    assert packet.chunks == (
        Chunk(SYNC + b"\x01Z00\x02AAHE", pause_after=0.1),
        Chunk(b"LL", pause_after=0.25),
        Chunk(b"O\x0301FB\x04"),
    )
