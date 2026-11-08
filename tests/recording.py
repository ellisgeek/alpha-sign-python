"""A Transport adapter that keeps every byte written and read, for hardware captures."""

from dataclasses import dataclass, field

from alpha_led_sign.transport import Transport

type Event = tuple[str, bytes | float]
"""("write", bytes), ("pause", seconds), or ("read", bytes)."""


@dataclass
class RecordingTransport:
    """Wraps a Transport and records what passes through it, in order.

    Reads that return nothing are not recorded, so ``events`` holds only real traffic
    and the silences the library asked for.
    """

    inner: Transport
    events: list[Event] = field(default_factory=list)

    def write(self, data: bytes) -> None:
        self.inner.write(data)
        self.events.append(("write", data))

    def pause(self, seconds: float) -> None:
        self.inner.pause(seconds)
        self.events.append(("pause", seconds))

    def read(self, timeout: float) -> bytes:
        data = self.inner.read(timeout)
        if data:
            self.events.append(("read", data))
        return data

    def close(self) -> None:
        self.inner.close()

    @property
    def written(self) -> bytes:
        """Every byte written, with the pauses left out."""
        return self._joined("write")

    @property
    def received(self) -> bytes:
        """Every byte read."""
        return self._joined("read")

    def to_json(self) -> list[dict[str, str | float]]:
        """The events as JSON-ready records. Bytes are hex, so nothing is lost."""
        return [
            {"event": kind, "hex": data.hex()}
            if isinstance(data, bytes)
            else {"event": kind, "seconds": data}
            for kind, data in self.events
        ]

    def _joined(self, wanted: str) -> bytes:
        return b"".join(
            data for kind, data in self.events if kind == wanted and isinstance(data, bytes)
        )
