"""Test adapters for the Transport seam."""

from dataclasses import dataclass, field


@dataclass
class FakeTransport:
    """Records what a Sign sends, and replays canned Responses to reads."""

    events: list[tuple[str, bytes | float]] = field(default_factory=list)
    responses: list[bytes] = field(default_factory=list)
    closed: bool = False
    read_timeouts: list[float] = field(default_factory=list)

    def write(self, data: bytes) -> None:
        self.events.append(("write", data))

    def pause(self, seconds: float) -> None:
        self.events.append(("pause", seconds))

    def read(self, timeout: float) -> bytes:
        self.read_timeouts.append(timeout)
        return self.responses.pop(0) if self.responses else b""

    def close(self) -> None:
        self.closed = True

    @property
    def written(self) -> bytes:
        """Every byte written, with the pauses left out."""
        return b"".join(data for kind, data in self.events if isinstance(data, bytes))
