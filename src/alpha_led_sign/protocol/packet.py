"""Packet framing (pp. 10-14): sync, header, Commands, end marker."""

import re
from collections.abc import Sequence
from dataclasses import dataclass

from alpha_led_sign.protocol.addresses import check_sign_address
from alpha_led_sign.protocol.commands import Command
from alpha_led_sign.protocol.response import ResponseError, ResponseItem

NUL = b"\x00"
SOH = b"\x01"
STX = b"\x02"
ETX = b"\x03"
EOT = b"\x04"
FRAMING_BYTES = frozenset(SOH + STX + ETX + EOT)
SYNC = NUL * 5


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
        data = command.encode_data()
        if not FRAMING_BYTES.isdisjoint(data):
            raise ValueError(f"{type(command).__name__} data contains a framing byte: {data!r}")
        body = command.code.encode("ascii") + data
        if etx:
            body += ETX
        if checksum:
            body += f"{compute_checksum(STX + body):04X}".encode("ascii")
        start = 0
        for offset, pause in command.pauses_in_data():
            split = len(command.code) + offset
            chunks.append(Chunk(pending + body[start:split], pause_after=pause))
            pending, start = b"", split
        pending += body[start:]
    chunks.append(Chunk(pending + EOT, pause_after=commands[-1].pause_after))
    return Packet(tuple(chunks))


def compute_checksum(data: bytes) -> int:
    """The 16-bit sum of ``data``, which runs from an STX through its ETX inclusive (p. 12)."""
    return sum(data) & 0xFFFF


__all__ = [
    "Chunk",
    "Packet",
    "ReceivedResponse",
    "Recipient",
    "ResponseError",
    "ResponseItem",
    "ResponseReader",
    "check_sign_address",
    "compute_checksum",
    "decode_response",
    "encode_packet",
]

RESPONSE_HEADER = b"000"
"""Response Type Code "0" and Sign Address "00", sent whatever the Sign's address (p. 19)."""


def decode_response(data: bytes) -> tuple[ResponseItem, ...]:
    """Decode a Response Packet (pp. 19, 36, 38) into its Commands, checking each checksum."""
    start = data.find(SOH)
    if start < 0 or data[:start].strip(NUL):
        raise ResponseError(f"no Response Packet header in {data!r}")
    position = start + len(SOH)
    if data[position : position + len(RESPONSE_HEADER)] != RESPONSE_HEADER:
        raise ResponseError(f"not a Response Packet (Type Code 0, Sign Address 00): {data!r}")
    position += len(RESPONSE_HEADER)

    items: list[ResponseItem] = []
    while data[position : position + 1] == STX:
        end = data.find(ETX, position)
        if end < 0 or end == position + 1:
            raise ResponseError(f"Response Command without a Command Code or ETX: {data!r}")
        framed = data[position : end + 1]
        sent = data[end + 1 : end + 5]
        if f"{compute_checksum(framed):04X}".encode("ascii") != sent:
            raise ResponseError(f"Response checksum {sent!r} does not match its data: {data!r}")
        items.append(ResponseItem(chr(framed[1]), framed[2:-1]))
        position = end + 5
    if not items or data[position:] != EOT:
        raise ResponseError(f"Response Packet must be Commands followed by EOT: {data!r}")
    return tuple(items)


type ReceivedResponse = tuple[ResponseItem, ...] | ResponseError
"""A Response Packet as received: its Commands, or the ResponseError it failed to decode with."""


class ResponseReader:
    """Splits the bytes a Sign sends back into Response Packets, however they arrive."""

    def __init__(self) -> None:
        self._buffer = b""

    @property
    def pending(self) -> bytes:
        """Bytes received since the last complete Response."""
        return self._buffer

    def feed(self, data: bytes) -> list[ReceivedResponse]:
        """Add received bytes; return the Responses they complete.

        A Packet that fails to decode comes back as its ResponseError, in order, so the
        caller decides whether to raise or skip it.
        """
        self._buffer += data
        responses: list[ReceivedResponse] = []
        while EOT in self._buffer:
            end = self._buffer.index(EOT) + 1
            packet, self._buffer = self._buffer[:end], self._buffer[end:]
            try:
                responses.append(decode_response(packet))
            except ResponseError as error:
                responses.append(error)
        return responses
