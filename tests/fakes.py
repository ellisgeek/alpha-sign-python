"""Test adapters for the Transport seam."""

from dataclasses import dataclass, field

STX = b"\x02"
EOT = b"\x04"


@dataclass
class _Rule:
    command: bytes
    responses: tuple[bytes, ...]
    delay: float


@dataclass
class FakeLine:
    """An in-memory Line, with a virtual clock, that answers what is written to it.

    ``answer(b"BC", ...)`` sets up the Responses that arrive once a Packet holding the
    Command ``BC`` (Read TEXT File C) has been written, ``delay`` seconds later. Each
    rule answers once, so a second Read needs a second rule. ``arrive`` puts bytes on
    the Line whatever is written, such as an answer already waiting.

    Time moves only when the library pauses, or when a read waits: a read gets the
    next delivery if it arrives within its timeout, and otherwise waits the whole
    timeout and gets nothing. ``clock`` reads the same time, for code that takes one.
    No real time passes.
    """

    now: float = 0.0
    events: list[tuple[str, bytes | float]] = field(default_factory=list)
    closed: bool = False
    _rules: list[_Rule] = field(default_factory=list)
    _deliveries: list[tuple[float, bytes]] = field(default_factory=list)
    _packet: bytes = b""

    def answer(self, command: bytes, *responses: bytes, delay: float = 0.0) -> None:
        """Once a Packet holding ``command`` is written, send ``responses`` back, one
        delivery each, ``delay`` seconds later."""
        self._rules.append(_Rule(command, responses, delay))

    def arrive(self, data: bytes, *, at: float | None = None) -> None:
        """Put ``data`` on the Line at time ``at`` (default: now)."""
        self._deliver(self.now if at is None else at, data)

    def clock(self) -> float:
        """The Line's time, in seconds."""
        return self.now

    def write(self, data: bytes) -> None:
        self.events.append(("write", data))
        self._packet += data
        while EOT in self._packet:
            end = self._packet.index(EOT) + 1
            packet, self._packet = self._packet[:end], self._packet[end:]
            self._answer(packet)

    def pause(self, seconds: float) -> None:
        self.events.append(("pause", seconds))
        self.now += seconds

    def read(self, timeout: float) -> bytes:
        if self._deliveries and self._deliveries[0][0] <= self.now + timeout:
            at, data = self._deliveries.pop(0)
            self.now = max(self.now, at)
            return data
        self.now += timeout
        return b""

    def close(self) -> None:
        self.closed = True

    @property
    def written(self) -> bytes:
        """Every byte written, with the pauses left out."""
        return b"".join(data for kind, data in self.events if isinstance(data, bytes))

    def _answer(self, packet: bytes) -> None:
        for rule in self._rules:
            if STX + rule.command in packet:
                self._rules.remove(rule)
                for response in rule.responses:
                    self._deliver(self.now + rule.delay, response)
                return

    def _deliver(self, at: float, data: bytes) -> None:
        self._deliveries.append((at, data))
        self._deliveries.sort(key=lambda delivery: delivery[0])
