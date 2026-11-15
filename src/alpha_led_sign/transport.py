"""Transports: how Packet bytes reach a Sign."""

import time
from enum import Enum
from types import TracebackType
from typing import Protocol, Self

import serial

from alpha_led_sign.protocol.packet import Packet


class Transport(Protocol):
    """The seam between the library and the wire.

    ``SerialTransport`` is the one the library ships. Write another to reach a Sign
    some other way, such as through a network bridge that has its own way of keeping
    pauses, or to record what the library sends in a test. Any class with these four
    methods works; it need not inherit from ``Transport``.
    """

    def write(self, data: bytes) -> None:
        """Send bytes, and return once they have left.

        A pause measured from the return must be silence on the line, so a
        buffered Transport flushes before it returns.

        Args:
            data: The bytes to send.
        """
        ...

    def pause(self, seconds: float) -> None:
        """Keep the line quiet for a time the protocol needs.

        Args:
            seconds: How long to send nothing.
        """
        ...

    def read(self, timeout: float) -> bytes:
        """Return the bytes that have arrived, waiting for some if there are none.

        Args:
            timeout: The longest time to wait for the first byte, in seconds. With 0,
                return only what has already arrived.

        Returns:
            The bytes received, or ``b""`` if none arrived in time.
        """
        ...

    def close(self) -> None:
        """Release the connection. The Transport is not used afterwards."""
        ...


class SerialFormat(Enum):
    """Data bits, parity, and stop bits (Table 3, p. 8). Alpha 1.0 Signs accept both.

    Attributes:
        EIGHT_N_ONE: 8 data bits, no parity, 1 stop bit. The library's default.
        SEVEN_E_TWO: 7 data bits, even parity, 2 stop bits.
    """

    EIGHT_N_ONE = (serial.EIGHTBITS, serial.PARITY_NONE, serial.STOPBITS_ONE)
    SEVEN_E_TWO = (serial.SEVENBITS, serial.PARITY_EVEN, serial.STOPBITS_TWO)


class SerialTransport:
    """A serial port, opened with pyserial's ``serial_for_url``.

    This class makes the protocol's pauses by flushing the port and then sleeping. A
    TCP bridge must keep those pauses on its serial side; one that merges writes can
    lose them, and a nested Packet then fails.

    Args:
        url: A device such as ``/dev/tty.usbserial-1410`` or ``COM3``, ``loop://`` for
            tests, or ``socket://host:port`` for a raw TCP serial bridge or the
            emulator.
        baudrate: The line speed. Alpha 1.0 Signs accept 1200 to 9600 baud.
        serial_format: Data bits, parity, and stop bits.

    Raises:
        serial.SerialException: The port can't be opened.

    Attributes:
        port: The open pyserial port.
    """

    def __init__(
        self,
        url: str,
        *,
        baudrate: int = 9600,
        serial_format: SerialFormat = SerialFormat.EIGHT_N_ONE,
    ) -> None:
        bytesize, parity, stopbits = serial_format.value
        self.port = serial.serial_for_url(
            url, baudrate=baudrate, bytesize=bytesize, parity=parity, stopbits=stopbits
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

    def write(self, data: bytes) -> None:
        """Write bytes and flush, so that they have left when this returns.

        Args:
            data: The bytes to send.
        """
        self.port.write(data)
        self.port.flush()  # return only once the bytes are on the line

    def pause(self, seconds: float) -> None:
        """Sleep, sending nothing.

        Args:
            seconds: How long to sleep.
        """
        time.sleep(seconds)

    def read(self, timeout: float) -> bytes:
        """Wait for the first byte, then return it with every byte waiting behind it.

        Args:
            timeout: The longest time to wait for the first byte, in seconds. With 0,
                return only what has already arrived.

        Returns:
            The bytes received, or ``b""`` if none arrived in time.
        """
        self.port.timeout = timeout
        first = self.port.read(1)
        if not first:
            return b""
        return first + self.port.read(self.port.in_waiting)

    def close(self) -> None:
        """Close the port."""
        self.port.close()


def send_packet(transport: Transport, packet: Packet) -> None:
    """Write a Packet, keeping the line quiet for each pause the protocol needs.

    Args:
        transport: Where to write.
        packet: The encoded Packet. Each Chunk is written, then followed by its
            pause.
    """
    for chunk in packet.chunks:
        transport.write(chunk.data)
        if chunk.pause_after:
            transport.pause(chunk.pause_after)
