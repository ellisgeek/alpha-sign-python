"""Responses: what a Sign sends back after a read Command, and how it is decoded."""

from dataclasses import dataclass

from alpha_led_sign.protocol.framing import EOT, ETX, NUL, SOH, STX, compute_checksum


class ResponseError(ValueError):
    """A Response Packet that is malformed, fails its Checksum, or can't be parsed.

    It is a ValueError. A read raises it rather than skip the Response.
    """


class UnexpectedResponseError(ResponseError):
    """A well-formed Response that answers a different Read.

    A read raises it when no other Read is waiting for an answer. While one is, the
    Response is taken as that Read's late answer and skipped.
    """


@dataclass(frozen=True)
class ResponseItem:
    """One Command in a Response.

    Attributes:
        code: The Command Code.
        data: The Data Field.
    """

    code: str
    data: bytes


RESPONSE_HEADER = b"000"
"""Response Type Code "0" and Sign Address "00", sent whatever the Sign's address (p. 19)."""


def decode_response(data: bytes) -> tuple[ResponseItem, ...]:
    """Decode a Response Packet (pp. 19, 36, 38) into its Commands.

    Args:
        data: One whole Response Packet, from the sync NULs through EOT.

    Returns:
        The Commands, in order.

    Raises:
        ResponseError: The header is not a Response's, a Command is malformed or
            fails its Checksum, or anything but EOT follows the Commands.
    """
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
    """Splits the bytes a Sign sends back into Response Packets, however they arrive.

    Feed it bytes as they come. It keeps the bytes of an unfinished Response until
    the rest arrives.
    """

    def __init__(self) -> None:
        self._buffer = b""

    @property
    def pending(self) -> bytes:
        """Bytes received since the last complete Response."""
        return self._buffer

    @property
    def has_partial(self) -> bool:
        """True if part of a Response is in: anything beyond the sync NULs before one."""
        return bool(self._buffer.strip(NUL))

    def feed(self, data: bytes) -> list[ReceivedResponse]:
        """Add received bytes.

        Args:
            data: The bytes received.

        Returns:
            Each Response the bytes complete, in order. A Packet that fails to
            decode comes back as its ResponseError, so the caller decides whether
            to raise it or skip it.
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
