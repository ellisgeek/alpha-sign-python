"""Matching Responses to the Reads that asked for them (docs/spec.md, "Read behavior").

Pure: the caller moves bytes between the Transport and a ResponseMatcher, and acts on
what comes back. The matcher keeps the receive buffer and counts the Reads sent whose
Response has not arrived, so a late answer to a Read that timed out is skipped, but
only as many as went unanswered. A garbled Response is never skipped.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from alpha_led_sign.protocol.commands import Command, Read
from alpha_led_sign.protocol.responses import (
    ResponseError,
    ResponseItem,
    ResponseReader,
    UnexpectedResponseError,
)


@dataclass(frozen=True)
class Answer[T]:
    """The parsed answer to the Read being waited for.

    Attributes:
        value: What the Read's ``parse`` returned.
    """

    value: T


@dataclass(frozen=True)
class Skipped:
    """A Response that belongs to something earlier.

    It is a late answer to another Read, or the rest of one that had begun before
    this Read was sent.
    """


type Outcome[T] = Answer[T] | Skipped | ResponseError
"""What one complete Response meant for the Read being waited for."""


class ResponseMatcher:
    """Matches the Responses a Sign sends back to the Reads sent to it.

    ``Sign.query`` uses one. The caller moves bytes between it and the Transport.
    """

    def __init__(self) -> None:
        self._reader = ResponseReader()
        self._unanswered = 0  # Reads sent whose Response has not arrived yet
        self._skip_next = False  # the next Response began before the Read now waited on

    @property
    def pending(self) -> bytes:
        """Bytes received since the last complete Response."""
        return self._reader.pending

    def discard(self, data: bytes) -> None:
        """Take bytes received before a Read is sent.

        Each complete Response is dropped, because it answers an earlier Read. A
        partial one is kept so that the rest of it can be skipped later.

        Args:
            data: The bytes received.
        """
        self._unanswered = max(self._unanswered - len(self._reader.feed(data)), 0)

    def sent(self, commands: Sequence[Command]) -> None:
        """Record that a Packet was sent. Its Reads now wait for Responses.

        Args:
            commands: The Packet's Commands.
        """
        reads = sum(isinstance(command, Read) for command in commands)
        if reads and self._reader.has_partial:
            self._skip_next = True
        self._unanswered += reads

    def feed[T](self, read: Read[T], data: bytes) -> list[Outcome[T]]:
        """Take bytes received while waiting for a Read.

        Args:
            read: The Read being waited for.
            data: The bytes received.

        Returns:
            What each Response the bytes complete means for ``read``, in order.
        """
        return [self._outcome(read, response) for response in self._reader.feed(data)]

    def _outcome[T](
        self, read: Read[T], response: tuple[ResponseItem, ...] | ResponseError
    ) -> Outcome[T]:
        self._unanswered = max(self._unanswered - 1, 0)
        if self._skip_next:
            self._skip_next = False
            return Skipped()
        if isinstance(response, ResponseError):
            return response
        if read.answered_by(response):
            try:
                return Answer(read.parse(response))
            except ResponseError as error:
                return error
        if self._unanswered:
            return Skipped()
        return UnexpectedResponseError(
            f"the Response does not answer {type(read).__name__}, and no other Read is "
            f"waiting for one: {response!r}"
        )
