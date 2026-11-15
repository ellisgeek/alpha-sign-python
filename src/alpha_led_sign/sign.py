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
    """The Sign stopped answering before its Response was complete.

    Raised by a read when no bytes arrive for ``read_timeout`` seconds. The usual
    causes are a wrong Sign Address or Sign Type, a wrong baud rate or serial format,
    or a cable that carries data to the Sign but not back.
    """


DEFAULT_LABEL = "A"
"""The TEXT File every Sign has at power-up (p. 17)."""


class Sign:
    """One Sign, or a group of Signs, reached through a Transport.

    Each task method builds the Commands for one job, checks them against the Sign
    Model, and sends them in one Packet. A method that takes a ``str`` reads it as
    markup (see ``alpha_led_sign.markup``).

    Use ``Sign.serial`` to open a serial port. Pass a Transport to the constructor to
    use something else, such as a test double. A Sign is a context manager that
    closes its Transport on exit. It has no locking, so use it from one thread.

    Args:
        transport: Where Packets are written and Responses are read.
        model: The Sign Model, which sets the Sign Type to address and the
            Capabilities to check content against. ``models.GENERIC`` reaches every
            Sign and checks only the Protocol Version.
        address: The Sign Address, 0-255, or a two-character hex pattern in which
            ``?`` matches any digit, such as ``"1?"``. 0 reaches every Sign of the
            Sign Type.
        strict: Raise ``UnsupportedCapability`` instead of warning when the model
            lacks something a Command uses.
        checksum: Send a Checksum after each Command so the Sign rejects damaged
            data.
        read_timeout: Seconds a read waits for each part of a Response.
        broadcast_reads: Allow reads to Sign Address 0 or a ``?`` pattern. Every
            matching Sign answers, so set it only when one Sign is on the line.

    Raises:
        ValueError: The Sign Address is out of range or is not a valid pattern.

    Attributes:
        transport: The Transport this Sign writes to and reads from.
        model: The Sign Model content is checked against.
        recipient: The Sign Type and Sign Address that Packets go to.
        strict: Whether validation raises instead of warning.
        checksum: Whether Commands are sent with Checksums.
        read_timeout: Seconds a read waits for each part of a Response.
        broadcast_reads: Whether reads may go to more than one Sign.

    Examples:
        ```python
        from alpha_led_sign import Sign, models

        with Sign.serial("/dev/ttyUSB0", model=models.ALPHA_4120C, address=1) as sign:
            sign.show("{color green}Hello")
        ```
    """

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
        """Open a Sign on a serial port.

        Args:
            url: A device such as ``/dev/ttyUSB0`` or ``COM3``, or any pyserial URL:
                ``socket://host:port`` for a serial-to-TCP bridge or the emulator,
                ``loop://`` for a loopback.
            model: The Sign Model (see the class).
            baudrate: The line speed. Alpha 1.0 Signs accept 1200 to 9600 baud.
            serial_format: Data bits, parity, and stop bits.
            address: The Sign Address or pattern (see the class).
            strict: Raise instead of warning on unsupported content.
            checksum: Send a Checksum after each Command.
            read_timeout: Seconds a read waits for each part of a Response.
            broadcast_reads: Allow reads to more than one Sign.

        Returns:
            A Sign that owns the opened port and closes it on ``close``.

        Raises:
            serial.SerialException: The port can't be opened.
            ValueError: The Sign Address is out of range or is not a valid pattern.
        """
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
        """Write ``content`` to a TEXT File and show it. The display blanks first.

        This is the shortest way to put text on a Sign: every Sign has TEXT File
        ``A`` at power-up, so it needs no Memory Configuration.

        Args:
            content: Markup such as ``"{color red}Hi"``, or a list of Segments. Plain
                text is valid markup; write ``{{`` and ``}}`` for literal braces. A
                string inside a list of Segments is literal text.
            mode: How the first Frame is shown, until a ``{frame ...}`` token.
            position: Where the first Frame is shown, until a ``{frame ...}`` token.
            label: The File Label of the TEXT File to write.

        Raises:
            MarkupError: The markup can't be read.
            ValueError: The File Label is invalid, or the text has a character that
                is not printable ASCII.
            UnsupportedCapability: The model lacks something the content uses, and
                the Sign is strict.

        Warns:
            UnsupportedCapabilityWarning: The model lacks something the content uses,
                and the Sign is not strict.

        Examples:
            ```python
            sign.show("Hello")
            sign.show("{color amber}Doors open at 7", mode=Mode.ROTATE)
            sign.show(["{literal braces}"])  # a list holds literal text
            ```
        """
        if isinstance(content, str):
            message = parse_markup(content, mode=mode, position=position)
        else:
            message = Message(Frame(mode, position, content))
        self.send(WriteText(label, message))

    def write_text(self, label: str, content: Message | Frame | str) -> None:
        """Replace the content of a TEXT File. The display blanks while it is written.

        To update part of the display without blanking it, put a ``StringRef`` in
        the TEXT File and change the STRING File with ``write_string``.

        Args:
            label: The File Label of the TEXT File.
            content: A Message, one Frame, or markup. Markup before any
                ``{frame ...}`` token is shown in one HOLD Frame that fills the
                display.

        Raises:
            MarkupError: The markup can't be read.
            ValueError: The File Label is invalid, the text has a character that is
                not printable ASCII, or ``label`` is the Priority TEXT File and the
                content is longer than 125 bytes.
            UnsupportedCapability: The model lacks something the content uses, and
                the Sign is strict.

        Warns:
            UnsupportedCapabilityWarning: The model lacks something the content uses,
                and the Sign is not strict.

        Examples:
            ```python
            sign.write_text("A", "{frame rotate top}Temp: {string T}{frame hold bottom}{time}")
            ```
        """
        self.send(WriteText(label, _as_message(content)))

    def write_string(self, label: str, content: str | Sequence[Segment]) -> None:
        """Replace the content of a STRING File. The display does not blank.

        Use a STRING File for values that change often, such as a reading or a
        score: a TEXT File shows it with ``{string LABEL}`` or ``StringRef``.

        Args:
            label: The File Label of the STRING File.
            content: Markup without ``{frame ...}`` tokens, or a list of Segments.
                Pass values from outside the program through ``escape_markup`` so
                that their braces stay literal.

        Raises:
            MarkupError: The markup can't be read, or it has a ``{frame}`` token.
            ValueError: The File Label is invalid, the content is longer than 125
                bytes, or it has a Control Code a STRING File can't hold (Table 19).
            UnsupportedCapability: The model lacks something the content uses, and
                the Sign is strict.

        Warns:
            UnsupportedCapabilityWarning: The model lacks something the content uses,
                and the Sign is not strict.

        Examples:
            ```python
            sign.write_string("T", escape_markup(f"{reading:.1f}F"))
            ```
        """
        if isinstance(content, str):
            content = parse_segments(content)
        self.send(WriteString(label, content))

    def priority(self, content: Message | Frame | str) -> None:
        """Show the Priority TEXT File in place of everything else until it is cleared.

        The Priority TEXT File (label ``0``) holds at most 125 bytes. Writing Run
        Times or Run Days also ends it.

        Args:
            content: A Message, one Frame, or markup, as for ``write_text``.

        Raises:
            MarkupError: The markup can't be read.
            ValueError: The content is longer than 125 bytes, or the text has a
                character that is not printable ASCII.
            UnsupportedCapability: The model lacks something the content uses, and
                the Sign is strict.

        Warns:
            UnsupportedCapabilityWarning: The model lacks something the content uses,
                and the Sign is not strict.
        """
        self.send(WriteText(PRIORITY_LABEL, _as_message(content)))

    def clear_priority(self) -> None:
        """End the Priority TEXT File. The Sign goes back to its Run Sequence."""
        self.send(WriteText(PRIORITY_LABEL, Message()))

    def configure_memory(self, files: Sequence[MemoryFile]) -> None:
        """Replace the Memory Configuration with ``files``.

        This ERASES EVERY FILE on the Sign, TEXT File ``A`` included. Do it once when
        you set a Sign up, then write the Files.

        Args:
            files: The TEXT, STRING, and DOTS PICTURE Files the Sign should have.
                Only the last one may be a TEXT File of size 0, which takes the rest
                of memory.

        Raises:
            ValueError: ``files`` is empty, or a TEXT File other than the last has
                size 0.
            UnsupportedCapability: The Files need more memory than the model has,
                counting its overhead for each File, and the Sign is strict.

        Warns:
            UnsupportedCapabilityWarning: The Files need more memory than the model
                has, and the Sign is not strict.

        Examples:
            ```python
            sign.configure_memory(
                [
                    TextFile("A", size=256),
                    StringFile("T", size=16),
                    DotsPictureFile("P", rows=7, columns=8),
                ]
            )
            ```
        """
        self.send(SetMemoryConfiguration(files))

    def clear_memory(self) -> None:
        """Erase every File and the Memory Configuration.

        The Sign needs 1.5 s after this before it reports its memory correctly, so
        the send waits that long before it returns.
        """
        self.send(ClearMemory())

    def soft_reset(self) -> None:
        """Restart the Sign through its power-up diagnostics. Memory is kept."""
        self.send(SoftReset())

    def set_time_format(self, time_format: TimeFormat) -> None:
        """Show the time in 12-hour (AM/PM) or 24-hour format.

        Args:
            time_format: The format for ``{time}`` and the CLOCK Mode.
        """
        self.send(SetTimeFormat(time_format))

    def run_sequence(
        self,
        labels: Iterable[str],
        *,
        order: RunOrder = RunOrder.BY_RUN_TIME,
        locked: bool = False,
    ) -> None:
        """Set the TEXT Files the Sign shows, and their order.

        Args:
            labels: The File Labels of 1 to 128 TEXT Files, in the order to show
                them. A string such as ``"ABC"`` works.
            order: Whether each File waits for its Run Time (the default), every
                File runs in turn, or each File is deleted after its Stop Time.
            locked: Stop the Run Sequence from being changed with the IR keyboard.

        Raises:
            ValueError: There are no labels or more than 128, or a File Label is
                invalid.
        """
        self.send(SetRunSequence(labels, order=order, locked=locked))

    def set_run_times(self, run_times: Mapping[str, RunTime]) -> None:
        """Set when each of these TEXT Files runs each day. Other Files keep theirs.

        Writing Run Times ends a Priority TEXT File (p. 20).

        Args:
            run_times: A Run Time for each File Label.

        Raises:
            ValueError: A File Label is invalid.

        Examples:
            ```python
            sign.set_run_times(
                {
                    "A": RunTime.between(time(8, 0), time(17, 0)),
                    "B": RunTime.ALWAYS,
                }
            )
            ```
        """
        self.send(SetRunTimes(run_times))

    def set_run_days(self, run_days: Mapping[str, RunDays]) -> None:
        """Set the days each of these TEXT Files runs on.

        Writing Run Days ends a Priority TEXT File (p. 20).

        Args:
            run_days: The Run Days for each File Label.

        Raises:
            ValueError: A File Label is invalid.
        """
        self.send(SetRunDays(run_days))

    def set_speaker(self, enabled: bool) -> None:
        """Turn the speaker on or off.

        The speaker is off by default (p. 21), and ``beep`` and ``tone`` make no
        sound until it is on.

        Args:
            enabled: True to turn the speaker on.
        """
        self.send(SetSpeaker(enabled))

    def tone(self, frequency: int, duration: int, repeats: int = 0) -> None:
        """Play a tone, then wait until it has finished.

        The Sign can't take data while the tone plays, so this returns only after
        the first play and every repeat. The manual gives no scale for
        ``frequency``, and a 4120C plays every value at the same pitch
        (docs/hardware-results.md).

        Args:
            frequency: The speaker setting, 0-254.
            duration: The length of one play, 1-15 tenths of a second.
            repeats: How many times to play it again, 0-15.

        Raises:
            ValueError: A value is out of range.
        """
        self.send(ProgrammableTone(frequency, duration, repeats))

    def set_sign_address(self, address: int, *, broadcast: bool = False) -> None:
        """Give the Sign a new Sign Address, and send to that address from now on.

        A Sign Address set by DIP switch takes over again after a power cycle
        (p. 26).

        Args:
            address: The new Sign Address, 0-255. Avoid 0: it is the broadcast
                address, so every Sign of the Sign Type acts on it.
            broadcast: Send even though this Sign object addresses Sign Address 0 or
                a ``?`` pattern. Every matching Sign then takes the same new address.

        Raises:
            ValueError: This Sign object addresses more than one Sign and
                ``broadcast`` is False, or ``address`` is not 0-255. Nothing is sent.
        """
        if not broadcast and self.recipient.reaches_several:
            raise ValueError(
                f"Sign Address {self.recipient.address!r} reaches every matching Sign, which "
                "would all take the new address; pass broadcast=True to do that anyway"
            )
        self.send(SetSignAddress(address))
        self.recipient = Recipient(self.recipient.sign_type, address)

    def set_clock(self, now: datetime) -> None:
        """Set the time, the date, and the day of the week in one Packet.

        Args:
            now: The time to set. Seconds and the time zone are ignored.

        Raises:
            ValueError: The year is outside 1997-2096, which a two-digit year can
                show.

        Examples:
            ```python
            sign.set_clock(datetime.now())
            ```
        """
        self.send(SetTime(now.time()), SetDate(now.date()), SetDayOfWeek(Weekday.of(now.date())))

    def beep(self, tone: Tone = Tone.THREE_BEEPS) -> None:
        """Sound a built-in tone, then wait 3 s while the Sign can't take data.

        Args:
            tone: Which built-in tone to play.
        """
        self.send(Beep(tone))

    def read_text(self, label: str = DEFAULT_LABEL) -> Message:
        """Read a TEXT File back. The display pauses while the Sign answers.

        Args:
            label: The File Label of the TEXT File.

        Returns:
            The TEXT File's content. ``to_markup`` turns it into markup.

        Raises:
            ValueError: The File Label is invalid, or this Sign object addresses more
                than one Sign and ``broadcast_reads`` is False.
            SignTimeoutError: No complete Response arrived.
            ResponseError: The Response is damaged or answers a different read.
        """
        return self.query(ReadText(label))

    def read_string(self, label: str) -> tuple[Segment, ...]:
        """Read a STRING File back.

        Args:
            label: The File Label of the STRING File.

        Returns:
            The STRING File's text and Control Codes, in order.

        Raises:
            ValueError: The File Label is invalid, or this Sign object addresses more
                than one Sign and ``broadcast_reads`` is False.
            SignTimeoutError: No complete Response arrived.
            ResponseError: The Response is damaged or answers a different read.
        """
        return self.query(ReadString(label))

    def write_dots_picture(self, label: str, picture: DotsPicture) -> None:
        """Write a SMALL DOTS PICTURE File. The display blanks until it is written.

        The picture's size must match the File's entry in the Memory Configuration
        (p. 39). The library does not keep track of that entry, so check the size
        yourself. A TEXT File shows the picture with ``{picture LABEL}`` or
        ``DotsPictureRef``.

        Args:
            label: The File Label of the DOTS PICTURE File.
            picture: The pixels to write.

        Raises:
            ValueError: The File Label is invalid.
            UnsupportedCapability: The model can't show pictures, the picture is
                larger than its display, or it uses colors a red-only model lacks,
                and the Sign is strict.

        Warns:
            UnsupportedCapabilityWarning: The same problems, when the Sign is not
                strict.
        """
        self.send(WriteDotsPicture(label, picture))

    def read_dots_picture(self, label: str) -> DotsPicture:
        """Read a SMALL DOTS PICTURE File back. The display pauses meanwhile.

        Args:
            label: The File Label of the DOTS PICTURE File.

        Returns:
            The picture, at the size the Sign reports.

        Raises:
            ValueError: The File Label is invalid, or this Sign object addresses more
                than one Sign and ``broadcast_reads`` is False.
            SignTimeoutError: No complete Response arrived.
            ResponseError: The Response is damaged or answers a different read.
        """
        return self.query(ReadDotsPicture(label))

    def info(self) -> GeneralInformation:
        """Read the Sign's firmware, clock, speaker, and memory details.

        Returns:
            What the Sign reports about itself.

        Raises:
            ValueError: This Sign object addresses more than one Sign and
                ``broadcast_reads`` is False.
            SignTimeoutError: No complete Response arrived.
            ResponseError: The Response is damaged or answers a different read.
        """
        return self.query(ReadGeneralInformation())

    def serial_errors(self) -> SerialErrorStatus:
        """Read the serial errors the Sign recorded since the last time they were read.

        Reading resets the record, so each call covers the Packets since the one
        before. ``.ok`` is True when every Packet arrived intact.

        Returns:
            The Sign's Serial Error Status Register.

        Raises:
            ValueError: This Sign object addresses more than one Sign and
                ``broadcast_reads`` is False.
            SignTimeoutError: No complete Response arrived.
            ResponseError: The Response is damaged or answers a different read.
        """
        return self.query(ReadSerialErrorStatus())

    def query[T](self, read: Read[T]) -> T:
        """Send one Read Command and return the Sign's answer.

        Bytes that arrived before the Read is sent are discarded. After that, a
        Response to some other kind of Read (a late answer to one that timed out) is
        skipped, but only as many as there are unanswered Reads. A late answer to the
        same kind of Read can't be told apart from the real one, so it is taken as
        the answer.

        Args:
            read: The Read Command to send.

        Returns:
            The answer, parsed by ``read``.

        Raises:
            ValueError: This Sign object addresses Sign Address 0 or a ``?`` pattern
                and ``broadcast_reads`` is False. Nothing is sent.
            SignTimeoutError: No complete Response arrived.
            ResponseError: The Response is damaged, or it can't be parsed.
            UnexpectedResponseError: The Response answers a different Read, and no
                other Read is waiting for an answer.
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
        """Check Commands against the Sign Model and send them in one Packet.

        The task methods all send through this. Call it directly to send Commands
        from ``alpha_led_sign.protocol`` that have no task method, or to nest several
        Commands in one Packet.

        Args:
            *commands: The Commands to send, in order.

        Raises:
            ValueError: There are no Commands, a Command that must be last is not
                last, or a Command's data contains a framing byte.
            UnsupportedCapability: The model lacks something a Command uses, and the
                Sign is strict. Nothing is sent.

        Warns:
            UnsupportedCapabilityWarning: The model lacks something a Command uses,
                and the Sign is not strict. The Packet is sent anyway.

        Examples:
            ```python
            from alpha_led_sign.protocol import ClearSerialErrorStatus, WriteString

            sign.send(ClearSerialErrorStatus(), WriteString("T", "72F"))
            ```
        """
        validate(self.model, commands, strict=self.strict)
        send_packet(self.transport, encode_packet(self.recipient, commands, checksum=self.checksum))
        self._responses.sent(commands)


def _as_message(content: Message | Frame | str) -> Message:
    if isinstance(content, Message):
        return content
    if isinstance(content, Frame):
        return Message(content)
    return parse_markup(content)
