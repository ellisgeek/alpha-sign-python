"""Sign: the facade most callers use."""

from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime
from types import TracebackType
from typing import Self

from alpha_led_sign import models
from alpha_led_sign.markup import parse_markup, parse_segments
from alpha_led_sign.models import SignModel, validate
from alpha_led_sign.protocol.codes import Mode, Position
from alpha_led_sign.protocol.commands import (
    PRIORITY_LABEL,
    Beep,
    ClearMemory,
    Command,
    GeneralInformation,
    ProgrammableTone,
    Read,
    ReadDotsPicture,
    ReadGeneralInformation,
    ReadSerialErrorStatus,
    ReadString,
    ReadText,
    RunDays,
    RunOrder,
    SerialErrorStatus,
    SetDate,
    SetDayOfWeek,
    SetMemoryConfiguration,
    SetRunDays,
    SetRunSequence,
    SetRunTimes,
    SetSignAddress,
    SetSpeaker,
    SetTime,
    SetTimeFormat,
    SoftReset,
    TimeFormat,
    Tone,
    Weekday,
    WriteDotsPicture,
    WriteString,
    WriteText,
)
from alpha_led_sign.protocol.matching import Answer, ResponseMatcher, Skipped
from alpha_led_sign.protocol.memory import MemoryFile, RunTime
from alpha_led_sign.protocol.message import Frame, Message, Segment
from alpha_led_sign.protocol.packet import Recipient, encode_packet
from alpha_led_sign.protocol.pictures import DotsPicture
from alpha_led_sign.transport import SerialFormat, SerialTransport, Transport, send_packet

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
        broadcast_reads: bool = False,
    ) -> None:
        self.transport = transport
        self.read_timeout = read_timeout
        self.model = model
        self.recipient = Recipient(model.sign_type, address)
        self.strict = strict
        self.checksum = checksum
        self.broadcast_reads = broadcast_reads
        """Send reads to Sign Address 0 or a ``?`` pattern. Every matching Sign answers,
        so set it only when exactly one Sign is on the line."""
        self._responses = ResponseMatcher()

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
        read_timeout: float = DEFAULT_READ_TIMEOUT,
        broadcast_reads: bool = False,
    ) -> "Sign":
        """Open a Sign on a serial port (or any pyserial URL, such as ``loop://``)."""
        transport = SerialTransport(url, baudrate=baudrate, serial_format=serial_format)
        return cls(
            transport,
            model=model,
            address=address,
            strict=strict,
            checksum=checksum,
            read_timeout=read_timeout,
            broadcast_reads=broadcast_reads,
        )

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
        """Show ``content`` in TEXT File ``label``. The display blanks first.

        A string is markup, such as ``"{color red}Hi"`` (``alpha_led_sign.markup``): plain
        text works, and ``{{`` and ``}}`` are literal braces. ``mode`` and ``position``
        apply until the first ``{frame ...}`` token. A string inside a list of
        Segments is literal.
        """
        if isinstance(content, str):
            message = parse_markup(content, mode=mode, position=position)
        else:
            message = Message(Frame(mode, position, content))
        self.send(WriteText(label, message))

    def write_text(self, label: str, content: Message | Frame | str) -> None:
        """Replace TEXT File ``label``. The display blanks while it is written.

        A string is markup (see ``show``). Before any ``{frame ...}`` token it is shown
        in one HOLD Frame that fills the display.
        """
        self.send(WriteText(label, _as_message(content)))

    def write_string(self, label: str, content: str | Sequence[Segment]) -> None:
        """Replace STRING File ``label``. The display does not blank: use it for live values.

        A string is markup (see ``show``) without ``{frame ...}`` tokens. Pass outside
        values through ``escape_markup`` so their braces stay literal.
        """
        if isinstance(content, str):
            content = parse_segments(content)
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

        Only the last File may be a TEXT File of size 0, which takes the rest of memory.
        The sizes plus the model's overhead per File must fit in its memory; a
        configuration that doesn't warns, or raises UnsupportedCapability when strict.
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

    def run_sequence(
        self,
        labels: Iterable[str],
        *,
        order: RunOrder = RunOrder.BY_RUN_TIME,
        locked: bool = False,
    ) -> None:
        """Show these TEXT Files, in this order.

        ``order`` says whether each File waits for its Run Time (the default), runs in
        turn regardless, or is deleted after its Stop Time. A locked Run Sequence can't
        be changed from the IR keyboard.
        """
        self.send(SetRunSequence(labels, order=order, locked=locked))

    def set_run_times(self, run_times: Mapping[str, RunTime]) -> None:
        """Set when each of these TEXT Files runs each day. Other Files keep theirs.

        Writing Run Times ends a Priority TEXT File (p. 20).
        """
        self.send(SetRunTimes(run_times))

    def set_run_days(self, run_days: Mapping[str, RunDays]) -> None:
        """Set the days each of these TEXT Files runs on.

        Writing Run Days ends a Priority TEXT File (p. 20).
        """
        self.send(SetRunDays(run_days))

    def set_speaker(self, enabled: bool) -> None:
        """Turn the speaker on or off. It is off by default (p. 21), and tones need it."""
        self.send(SetSpeaker(enabled))

    def tone(self, frequency: int, duration: int, repeats: int = 0) -> None:
        """Play a tone: ``frequency`` 0-254, ``duration`` 1-15 tenths of a second.

        The manual gives no scale for ``frequency``, and a 4120C ignores it: every value
        plays at the same pitch (docs/hardware-results.md).

        The Sign can't take data while the tone plays, so this waits until the tone
        has finished, counting the first play and every repeat.
        """
        self.send(ProgrammableTone(frequency, duration, repeats))

    def set_sign_address(self, address: int, *, broadcast: bool = False) -> None:
        """Give the Sign a new Sign Address, then address it there.

        Sent to Sign Address 0 or to a pattern with ``?``, this reaches every matching
        Sign and gives them all the same address, so it is refused unless
        ``broadcast=True``. A DIP switch address wins after a power cycle (p. 26).
        """
        if not broadcast and self.recipient.reaches_several:
            raise ValueError(
                f"Sign Address {self.recipient.address!r} reaches every matching Sign, which "
                "would all take the new address; pass broadcast=True to do that anyway"
            )
        self.send(SetSignAddress(address))
        self.recipient = Recipient(self.recipient.sign_type, address)

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

    def write_dots_picture(self, label: str, picture: DotsPicture) -> None:
        """Write a SMALL DOTS PICTURE File. The display blanks until the picture is in.

        The picture's size must match the File's entry in the Memory Configuration
        (p. 39); the library does not track that, so check it yourself. A TEXT File
        shows the picture with ``DotsPictureRef(label)``.
        """
        self.send(WriteDotsPicture(label, picture))

    def read_dots_picture(self, label: str) -> DotsPicture:
        """Read SMALL DOTS PICTURE File ``label`` back. The display pauses meanwhile."""
        return self.query(ReadDotsPicture(label))

    def info(self) -> GeneralInformation:
        """Read firmware, clock, speaker, and memory details."""
        return self.query(ReadGeneralInformation())

    def serial_errors(self) -> SerialErrorStatus:
        """Read the errors recorded since the last read. Reading resets the register."""
        return self.query(ReadSerialErrorStatus())

    def query[T](self, read: Read[T]) -> T:
        """Send one Read Command and parse the Sign's Response.

        Only the addressed Sign may answer, so a Read to Sign Address 0 or a ``?``
        pattern is refused unless ``broadcast_reads`` is set. Anything received before
        the Read is sent is discarded. After that, a Response to some
        other Read (a late answer to one that timed out) is skipped, but only as many
        as there are unanswered Reads. A late answer to the same kind of Read can't be
        told apart from the real one, so it is taken as the answer.
        """
        if self.recipient.reaches_several and not self.broadcast_reads:
            raise ValueError(
                f"Sign Address {self.recipient.address!r} reaches every matching Sign, and "
                "their answers would collide; address one Sign (discover() finds them), or "
                "pass broadcast_reads=True when only one Sign is on the line"
            )
        while data := self.transport.read(0):
            self._responses.discard(data)
        self.send(read)
        while True:
            data = self.transport.read(self.read_timeout)
            if not data:
                raise SignTimeoutError(f"no complete Response after {self._responses.pending!r}")
            for outcome in self._responses.feed(read, data):
                match outcome:
                    case Answer(value):
                        return value
                    case Skipped():
                        continue
                    case error:
                        raise error

    def send(self, *commands: Command) -> None:
        """Validate ``commands`` against the model and send them in one Packet."""
        validate(self.model, commands, strict=self.strict)
        send_packet(self.transport, encode_packet(self.recipient, commands, checksum=self.checksum))
        self._responses.sent(commands)


def _as_message(content: Message | Frame | str) -> Message:
    if isinstance(content, Message):
        return content
    if isinstance(content, Frame):
        return Message(content)
    return parse_markup(content)
