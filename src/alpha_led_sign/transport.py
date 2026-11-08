"""Transports: how Packet bytes reach a Sign."""

import time
from enum import Enum
from types import TracebackType
from typing import Protocol, Self

import serial


class Transport(Protocol):
    """The seam between the library and the wire.

    ``write`` returns once the bytes have left (so that a pause measured after it is
    real silence on the line), and ``pause`` keeps the line quiet for that long.
    """

    def write(self, data: bytes) -> None: ...

    def pause(self, seconds: float) -> None: ...

    def read(self, timeout: float) -> bytes: ...

    def close(self) -> None: ...


class SerialFormat(Enum):
    """Data bits, parity, and stop bits (Table 3, p. 8). Alpha 1.0 Signs accept both."""

    EIGHT_N_ONE = (serial.EIGHTBITS, serial.PARITY_NONE, serial.STOPBITS_ONE)
    SEVEN_E_TWO = (serial.SEVENBITS, serial.PARITY_EVEN, serial.STOPBITS_TWO)


class SerialTransport:
    """A serial port, opened with pyserial's ``serial_for_url``.

    ``url`` can be a device such as ``/dev/tty.usbserial-1410``, ``loop://`` for tests,
    or ``socket://host:port`` for a raw TCP serial bridge. A bridge must keep the
    pauses the protocol needs, which this class creates by flushing and then waiting.
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
        self.port.write(data)
        self.port.flush()  # return only once the bytes are on the line

    def pause(self, seconds: float) -> None:
        time.sleep(seconds)

    def read(self, timeout: float) -> bytes:
        """Wait up to ``timeout`` seconds for data; return what has arrived, or b""."""
        self.port.timeout = timeout
        first = self.port.read(1)
        if not first:
            return b""
        return first + self.port.read(self.port.in_waiting)

    def close(self) -> None:
        self.port.close()
