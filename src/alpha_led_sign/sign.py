"""Sign: the facade most callers use."""

from collections.abc import Iterable, Sequence
from datetime import datetime
from types import TracebackType
from typing import Self

from alpha_led_sign import models
from alpha_led_sign.models import SignModel, validate
from alpha_led_sign.protocol.codes import Mode, Position
from alpha_led_sign.protocol.commands import (
    PRIORITY_LABEL,
    Beep,
    ClearMemory,
    Command,
    GeneralInformation,
    Read,
    ReadGeneralInformation,
    ReadSerialErrorStatus,
    ReadString,
    ReadText,
    SerialErrorStatus,
    SetDate,
    SetDayOfWeek,
    SetMemoryConfiguration,
    SetRunSequence,
    SetTime,
    SetTimeFormat,
    SoftReset,
    TimeFormat,
    Tone,
    Weekday,
    WriteString,
    WriteText,
)
from alpha_led_sign.protocol.memory import MemoryFile
from alpha_led_sign.protocol.message import Frame, Message, Segment
from alpha_led_sign.protocol.packet import EOT, Packet, Recipient, decode_response, encode_packet
from alpha_led_sign.transport import SerialFormat, SerialTransport, Transport

DEFAULT_READ_TIMEOUT = 2.0
"""Seconds to wait for each part of a Response before giving up."""


class SignTimeoutError(TimeoutError):
    """The Sign stopped answering before its Response was complete."""


DEFAULT_LABEL = "A"
"""The TEXT File every Sign has at power-up (p. 17)."""


class Sign:
    """One Sign (or group of Signs) reached through a Transport."""

    def __init__(
        self,
        transport: Transport,
        *,
        model: SignModel = models.GENERIC,
        address: int | str = 0,
        strict: bool = False,
        checksum: bool = True,
        read_timeout: float = DEFAULT_READ_TIMEOUT,
    ) -> None:
        self.transport = transport
        self.read_timeout = read_timeout
        self.model = model
        self.recipient = Recipient(model.sign_type, address)
        self.strict = strict
        self.checksum = checksum

    @classmethod
    def serial(
        cls,
        url: str,
        *,
        model: SignModel = models.GENERIC,
        baudrate: int = 9600,
        serial_format: SerialFormat = SerialFormat.EIGHT_N_ONE,
        address: int | str = 0,
        strict: bool = False,
        checksum: bool = True,
    ) -> "Sign":
        """Open a Sign on a serial port (or any pyserial URL, such as ``loop://``)."""
        transport = SerialTransport(url, baudrate=baudrate, serial_format=serial_format)
        return cls(transport, model=model, address=address, strict=strict, checksum=checksum)

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        """Close the Transport."""
        self.transport.close()

    def show(
        self,
        content: str | Sequence[Segment],
        *,
        mode: Mode = Mode.HOLD,
        position: Position = Position.FILL,
        label: str = DEFAULT_LABEL,
    ) -> None:
        """Show ``content`` in one Frame of TEXT File ``label``. The display blanks first."""
        self.send(WriteText(label, Message(Frame(mode, position, content))))

    def write_text(self, label: str, content: Message | Frame | str) -> None:
        """Replace TEXT File ``label``. The display blanks while it is written.

        Plain text is shown in one HOLD Frame that fills the display.
        """
        self.send(WriteText(label, _as_message(content)))

    def write_string(self, label: str, content: str | Sequence[Segment]) -> None:
        """Replace STRING File ``label``. The display does not blank: use it for live values."""
        self.send(WriteString(label, content))

    def priority(self, content: Message | Frame | str) -> None:
        """Show the Priority TEXT File, which replaces everything else until cleared."""
        self.send(WriteText(PRIORITY_LABEL, _as_message(content)))

    def clear_priority(self) -> None:
        """End the Priority TEXT File; the Sign goes back to its Run Sequence."""
        self.send(WriteText(PRIORITY_LABEL, Message()))

    def configure_memory(self, files: Sequence[MemoryFile]) -> None:
        """Replace the Memory Configuration with ``files``.

        This ERASES EVERY FILE on the Sign, including TEXT File "A". Do it once when
        setting a Sign up, then write the Files.
        """
        self.send(SetMemoryConfiguration(files))

    def clear_memory(self) -> None:
        """Erase every File and the Memory Configuration."""
        self.send(ClearMemory())

    def soft_reset(self) -> None:
        """Restart the Sign through its power-up diagnostics. Memory is kept."""
        self.send(SoftReset())

    def set_time_format(self, time_format: TimeFormat) -> None:
        """Show the time in 12-hour (am/pm) or 24-hour format."""
        self.send(SetTimeFormat(time_format))

    def run_sequence(self, labels: Iterable[str]) -> None:
        """Show these TEXT Files, in this order, each during its Run Time."""
        self.send(SetRunSequence(labels))

    def set_clock(self, now: datetime) -> None:
        """Set the time, date, and day of the week in one Packet. Seconds are dropped."""
        self.send(SetTime(now.time()), SetDate(now.date()), SetDayOfWeek(Weekday.of(now.date())))

    def beep(self, tone: Tone = Tone.THREE_BEEPS) -> None:
        """Sound a built-in tone. The Sign can't take data for about 3 s afterwards."""
        self.send(Beep(tone))

    def read_text(self, label: str = DEFAULT_LABEL) -> Message:
        """Read TEXT File ``label`` back. The display pauses while the Sign answers."""
        return self.query(ReadText(label))

    def read_string(self, label: str) -> tuple[Segment, ...]:
        """Read STRING File ``label`` back: its text and Control Codes."""
        return self.query(ReadString(label))

    def info(self) -> GeneralInformation:
        """Read firmware, clock, speaker, and memory details."""
        return self.query(ReadGeneralInformation())

    def serial_errors(self) -> SerialErrorStatus:
        """Read the errors recorded since the last read. Reading resets the register."""
        return self.query(ReadSerialErrorStatus())

    def query[T](self, read: Read[T]) -> T:
        """Send one Read Command and parse the Sign's Response.

        Use one Sign Address per Sign: only the addressed Sign may answer.
        """
        self.send(read)
        return read.parse(decode_response(self._receive()))

    def _receive(self) -> bytes:
        received = b""
        while EOT not in received:
            data = self.transport.read(self.read_timeout)
            if not data:
                raise SignTimeoutError(f"no complete Response after {received!r}")
            received += data
        return received[: received.index(EOT) + 1]

    def send(self, *commands: Command) -> None:
        """Validate ``commands`` against the model and send them in one Packet."""
        validate(self.model, commands, strict=self.strict)
        self._send(encode_packet(self.recipient, commands, checksum=self.checksum))

    def _send(self, packet: Packet) -> None:
        for chunk in packet.chunks:
            self.transport.write(chunk.data)
            if chunk.pause_after:
                self.transport.pause(chunk.pause_after)


def _as_message(content: Message | Frame | str) -> Message:
    if isinstance(content, Message):
        return content
    if isinstance(content, Frame):
        return Message(content)
    return Message(Frame(Mode.HOLD, Position.FILL, content))
