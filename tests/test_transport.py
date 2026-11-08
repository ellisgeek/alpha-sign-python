"""SerialTransport over pyserial's loop:// URL: bytes written come straight back."""

from alpha_led_sign import Sign
from alpha_led_sign.transport import SerialFormat, SerialTransport


def test_serial_transport_defaults_to_9600_8n1() -> None:
    # Table 3, p. 8: Alpha 1.0 runs at up to 9600 baud, 7E2 or 8N1.
    with SerialTransport("loop://") as transport:
        port = transport.port
        assert (port.baudrate, port.bytesize, port.parity, port.stopbits) == (9600, 8, "N", 1)


def test_serial_transport_can_use_7e2() -> None:
    with SerialTransport("loop://", baudrate=2400, serial_format=SerialFormat.SEVEN_E_TWO) as t:
        assert (t.port.baudrate, t.port.bytesize, t.port.parity, t.port.stopbits) == (
            2400,
            7,
            "E",
            2,
        )


def test_bytes_written_can_be_read_back_on_a_loop() -> None:
    with SerialTransport("loop://") as transport:
        transport.write(b"\x01Z00\x02AAHELLO\x04")
        transport.pause(0.001)

        assert transport.read(timeout=0.5) == b"\x01Z00\x02AAHELLO\x04"
        assert transport.read(timeout=0.01) == b""


def test_sign_serial_opens_a_serial_transport() -> None:
    with Sign.serial("loop://") as sign:
        sign.show("hi")

        assert isinstance(sign.transport, SerialTransport)
        assert sign.transport.read(timeout=0.5).endswith(b"hi\x030205\x04")
