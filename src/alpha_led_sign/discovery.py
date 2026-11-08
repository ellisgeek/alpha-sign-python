"""Find the Signs on a network, and their Sign Addresses, with a Network Query."""

import time
import warnings
from dataclasses import dataclass

from alpha_led_sign import models
from alpha_led_sign.models import SignModel
from alpha_led_sign.protocol.commands import NetworkQuery, SerialErrorStatus
from alpha_led_sign.protocol.packet import (
    ReceivedResponse,
    Recipient,
    ResponseReader,
    encode_packet,
)
from alpha_led_sign.protocol.response import ResponseError
from alpha_led_sign.transport import Transport, send_packet

FIRST_ANSWER_DELAY = 1.0
"""Seconds before the Sign at address 0 answers (p. 32)."""
PER_ADDRESS_DELAY = 0.5
"""Extra seconds each address waits before answering (p. 32)."""
MARGIN = 1.0
"""Extra seconds to wait after the last expected answer."""


@dataclass(frozen=True)
class DiscoveredSign:
    """A Sign that answered a Network Query."""

    sign_type: str
    address: int
    errors: SerialErrorStatus

    @property
    def model(self) -> SignModel | None:
        """The registered Sign Model with this Sign Type, if there is exactly one."""
        matches = [m for m in models.REGISTRY.values() if m.sign_type == self.sign_type]
        return matches[0] if len(matches) == 1 else None


def discover(
    transport: Transport, *, max_address: int = 255, checksum: bool = True
) -> list[DiscoveredSign]:
    """Broadcast a Network Query and collect every answer, sorted by Sign Address.

    Signs answer one after another, 1 s + 0.5 s x their address after the query, so
    searching all 255 addresses takes over two minutes. Lower ``max_address`` when the
    Signs' addresses are known to be small. Two Signs sharing an address garble each
    other's answers (p. 32); those answers are skipped with a warning.
    """
    if not 0 <= max_address <= 0xFF:
        raise ValueError(f"max_address must be 0-255, got {max_address}")
    broadcast = Recipient(models.GENERIC.sign_type, 0)
    send_packet(transport, encode_packet(broadcast, [NetworkQuery()], checksum=checksum))
    wait = FIRST_ANSWER_DELAY + max_address * PER_ADDRESS_DELAY + MARGIN
    deadline = time.monotonic() + wait

    found: dict[int, DiscoveredSign] = {}
    reader = ResponseReader()
    while (remaining := deadline - time.monotonic()) > 0:
        data = transport.read(remaining)
        if not data:
            break
        for response in reader.feed(data):
            _collect(response, found)
    if reader.pending.strip(b"\x00"):
        _garbled(reader.pending)
    return sorted(found.values(), key=lambda sign: sign.address)


def _collect(response: ReceivedResponse, found: dict[int, DiscoveredSign]) -> None:
    if isinstance(response, ResponseError):
        _garbled(response)
        return
    try:
        answer = NetworkQuery().parse(response)
    except ResponseError as error:
        _garbled(error)
        return
    found[answer.address] = DiscoveredSign(answer.sign_type, answer.address, answer.errors)


def _garbled(detail: bytes | ResponseError) -> None:
    """Warn about an answer that could not be read: its leftover bytes, or why it failed."""
    warnings.warn(
        f"skipped a garbled Network Query answer (do two Signs share an address?): {detail}",
        stacklevel=3,
    )
