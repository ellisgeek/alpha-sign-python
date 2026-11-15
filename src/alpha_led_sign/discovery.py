"""Find the Signs on a network, and their Sign Addresses, with a Network Query."""

import time
import warnings
from collections.abc import Callable
from dataclasses import dataclass

from alpha_led_sign import models
from alpha_led_sign.models import SignModel
from alpha_led_sign.protocol.addresses import check_sign_address
from alpha_led_sign.protocol.commands import NetworkQuery, SerialErrorStatus
from alpha_led_sign.protocol.packet import Recipient, encode_packet
from alpha_led_sign.protocol.responses import ReceivedResponse, ResponseError, ResponseReader
from alpha_led_sign.transport import Transport, send_packet

FIRST_ANSWER_DELAY = 1.0
"""Seconds before the Sign at address 0 answers (p. 32)."""
PER_ADDRESS_DELAY = 0.5
"""Extra seconds each address waits before answering (p. 32)."""
MARGIN = 1.0
"""Extra seconds to wait after the last expected answer."""


@dataclass(frozen=True)
class DiscoveredSign:
    """A Sign that answered a Network Query.

    Attributes:
        sign_type: The Sign's one-character Sign Type.
        address: The Sign's Sign Address.
        errors: The Sign's Serial Error Status Register when it answered.
    """

    sign_type: str
    address: int
    errors: SerialErrorStatus

    @property
    def model(self) -> SignModel | None:
        """The registered Sign Model with this Sign Type.

        None when no model, or more than one, has the Sign Type.
        """
        return models.by_sign_type(self.sign_type)


def discover(
    transport: Transport,
    *,
    max_address: int = 255,
    checksum: bool = True,
    clock: Callable[[], float] = time.monotonic,
) -> list[DiscoveredSign]:
    """Find the Signs on a line and their Sign Addresses.

    This broadcasts a Network Query to every Sign and collects the answers. Each
    Sign answers 1 s + 0.5 s x its Sign Address after the query, so a search of all
    255 addresses takes over two minutes. Lower ``max_address`` when the addresses
    are known to be small. A Sign ignores other Commands until it has answered.

    Two Signs that share an address garble each other's answers (p. 32). Those
    answers are skipped with a warning.

    Args:
        transport: The line to search. Discovery takes a Transport, not a Sign,
            because it reaches every Sign Type.
        max_address: The highest Sign Address to wait for, 0-255.
        checksum: Send the query with a Checksum.
        clock: Returns the time in seconds. The wait for answers is measured on it.

    Returns:
        One entry for each Sign that answered, sorted by Sign Address.

    Raises:
        ValueError: ``max_address`` is not 0-255.

    Warns:
        UserWarning: An answer was garbled and skipped.

    Examples:
        ```python
        from alpha_led_sign import SerialTransport, discover

        with SerialTransport("/dev/ttyUSB0") as line:
            for found in discover(line, max_address=15):
                print(found.address, found.sign_type, found.model)
        ```
    """
    check_sign_address(max_address, name="max_address")
    broadcast = Recipient(models.GENERIC.sign_type, 0)
    send_packet(transport, encode_packet(broadcast, [NetworkQuery()], checksum=checksum))
    wait = FIRST_ANSWER_DELAY + max_address * PER_ADDRESS_DELAY + MARGIN
    deadline = clock() + wait

    found: dict[int, DiscoveredSign] = {}
    reader = ResponseReader()
    while (remaining := deadline - clock()) > 0:
        data = transport.read(remaining)
        if not data:
            break
        for response in reader.feed(data):
            _collect(response, found)
    if reader.has_partial:
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
