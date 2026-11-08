"""Commands: one instruction inside a Packet, a Command Code plus its data."""

from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass
from typing import ClassVar

from alpha_led_sign.protocol.labels import check_file_label
from alpha_led_sign.protocol.message import Message
from alpha_led_sign.protocol.versions import ProtocolVersion


class Command(ABC):
    """One Command. Subclasses set ``code`` and implement ``encode_data``."""

    code: ClassVar[str]
    """The one-character Command Code (Table 6, p. 11)."""

    pause_after: ClassVar[float] = 0.0
    """Seconds of silence the Sign needs after this Command before it can take more data."""

    must_be_last: ClassVar[bool] = False
    """True if this Command may only be the last one in a nested Packet (p. 11)."""

    min_version: ClassVar[ProtocolVersion] = ProtocolVersion.EZ_KEY_II
    """The earliest Protocol Version that has this Command."""

    @abstractmethod
    def encode_data(self) -> bytes:
        """Return the Data Field that follows the Command Code."""

    def codes(self) -> Iterable[object]:
        """The Modes, Display Positions, and Control Codes in this Command's data."""
        return ()


PRIORITY_LABEL = "0"
"""The File Label of the Priority TEXT File (p. 20). Writing an empty Message to it clears it."""

PRIORITY_MAX_BYTES = 125
"""The Priority TEXT File's fixed size (p. 20)."""


@dataclass(frozen=True)
class WriteText(Command):
    """Write a Message to a TEXT File (p. 18). Writing blanks the display."""

    code: ClassVar[str] = "A"
    label: str
    message: Message

    def __post_init__(self) -> None:
        check_file_label(self.label)
        if self.label == PRIORITY_LABEL and len(self.message.encode()) > PRIORITY_MAX_BYTES:
            raise ValueError(
                f"the Priority TEXT File holds at most {PRIORITY_MAX_BYTES} bytes, "
                f"and this Message encodes to {len(self.message.encode())}"
            )

    def encode_data(self) -> bytes:
        return self.label.encode("ascii") + self.message.encode()

    def codes(self) -> Iterable[object]:
        return self.message.codes()
