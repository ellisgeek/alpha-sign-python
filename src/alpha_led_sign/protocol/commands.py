"""Commands: one instruction inside a Packet, a Command Code plus its data."""

from abc import ABC, abstractmethod
from typing import ClassVar


class Command(ABC):
    """One Command. Subclasses set ``code`` and implement ``encode_data``."""

    code: ClassVar[str]
    """The one-character Command Code (Table 6, p. 11)."""

    pause_after: ClassVar[float] = 0.0
    """Seconds of silence the Sign needs after this Command before it can take more data."""

    must_be_last: ClassVar[bool] = False
    """True if this Command may only be the last one in a nested Packet (p. 11)."""

    @abstractmethod
    def encode_data(self) -> bytes:
        """Return the Data Field that follows the Command Code."""
