"""What a Sign sends back: the Commands inside a Response Packet."""

from dataclasses import dataclass


class ResponseError(ValueError):
    """A Response Packet that is malformed, fails its checksum, or answers something else."""


@dataclass(frozen=True)
class ResponseItem:
    """One Command in a Response: its Command Code and Data Field."""

    code: str
    data: bytes
