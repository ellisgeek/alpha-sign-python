"""Packet framing (pp. 10-14): sync, header, Commands, end marker."""

import re
from collections.abc import Sequence
from dataclasses import dataclass

from alpha_led_sign.protocol.addresses import check_sign_address
from alpha_led_sign.protocol.commands import Command, Pause
from alpha_led_sign.protocol.framing import (
    EOT,
    ETX,
    FRAMING_BYTES,
    SOH,
    STX,
    SYNC,
    compute_checksum,
)

_ADDRESS_PATTERN = re.compile(r"[0-9A-F?]{2}")


@dataclass(frozen=True)
class Recipient:
    """One Sign Type and Sign Address pair.

    ``address`` is 0-255 (0 is broadcast), or a two-character hex pattern in which ``?``
    matches any digit: ``"1?"`` selects addresses 10H-1FH (p. 11).
    """

    sign_type: str
    address: int | str

    def __post_init__(self) -> None:
        if len(self.sign_type) != 1 or not self.sign_type.isascii():
            raise ValueError(f"Sign Type must be one ASCII character, got {self.sign_type!r}")
        if isinstance(self.address, int):
            check_sign_address(self.address)
        elif not _ADDRESS_PATTERN.fullmatch(self.address):
            raise ValueError(
                f"Sign Address pattern must be two hex digits or '?', got {self.address!r}"
            )

    @property
    def reaches_several(self) -> bool:
        """True for broadcast (address 0) or a ``?`` pattern: more than one Sign may act."""
        if isinstance(self.address, int):
            return self.address == 0
        return "?" in self.address or int(self.address, 16) == 0

    def encode(self) -> bytes:
        if isinstance(self.address, int):
            return f"{self.sign_type}{self.address:02X}".encode("ascii")
        return f"{self.sign_type}{self.address}".encode("ascii")


NESTED_STX_PAUSE = 0.1
"""Seconds of silence a nested Packet needs after each STX (pp. 11, 13, 14)."""


@dataclass(frozen=True)
class Chunk:
    """Bytes to send in one go, then ``pause_after`` seconds of silence before the next."""

    data: bytes
    pause_after: float = 0.0


@dataclass(frozen=True)
class Packet:
    """An encoded Packet, split where the protocol needs the line to go quiet.

    Sending it means writing each chunk and sleeping for its pause. ``bytes(packet)``
    gives the whole Packet with no pauses, for logging and comparison.
    """

    chunks: tuple[Chunk, ...]

    def __bytes__(self) -> bytes:
        return b"".join(chunk.data for chunk in self.chunks)


def _split_pauses(
    encoded: bytes | Sequence[bytes | Pause],
) -> tuple[bytes, list[tuple[int, float]]]:
    """A Command's Data Field, and each pause in it as (offset into the data, seconds)."""
    if isinstance(encoded, bytes):
        return encoded, []
    data, pauses = b"", []
    for piece in encoded:
        if isinstance(piece, Pause):
            pauses.append((len(data), piece.seconds))
        else:
            data += piece
    return data, pauses


def encode_packet(
    recipients: Recipient | Sequence[Recipient],
    commands: Sequence[Command],
    *,
    checksum: bool = True,
) -> Packet:
    """Encode one Packet that sends ``commands``, in order, to every Recipient."""
    if isinstance(recipients, Recipient):
        recipients = [recipients]
    if not commands:
        raise ValueError("a Packet needs at least one Command")
    for command in commands[:-1]:
        if command.must_be_last:
            raise ValueError(f"{type(command).__name__} must be the last Command in a Packet")
    nested = len(commands) > 1
    # A lone Command without a Checksum needs no ETX (Table 38). Nested ones always end in
    # ETX, which is how the Sign knows another STX may follow (p. 14).
    etx = checksum or nested

    chunks: list[Chunk] = []
    pending = SYNC + SOH + b",".join(r.encode() for r in recipients)
    for command in commands:
        pending += STX
        if nested:
            chunks.append(Chunk(pending, pause_after=NESTED_STX_PAUSE))
            pending = b""
        data, pauses = _split_pauses(command.encode_data())
        if not FRAMING_BYTES.isdisjoint(data):
            raise ValueError(f"{type(command).__name__} data contains a framing byte: {data!r}")
        body = command.code.encode("ascii") + data
        if etx:
            body += ETX
        if checksum:
            body += f"{compute_checksum(STX + body):04X}".encode("ascii")
        start = 0
        for offset, pause in pauses:
            split = len(command.code) + offset
            chunks.append(Chunk(pending + body[start:split], pause_after=pause))
            pending, start = b"", split
        pending += body[start:]
    chunks.append(Chunk(pending + EOT, pause_after=commands[-1].pause_after))
    return Packet(tuple(chunks))
