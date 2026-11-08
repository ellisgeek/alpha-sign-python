"""How fast can new data be pushed to a Sign?

Writes bursts of updates as fast as the library can send them and reports updates
per second, the bytes each update puts on the wire, and the most a serial line at
the given baud rate could carry. After each burst it reads the last value back and
checks the Serial Error Status Register, so a Sign that drops data or overflows its
buffer shows up as a failure rather than as a fast number.

- STRING File writes are the way to show live data: the display does not blank (p. 37).
- TEXT File writes are timed for comparison: the display blanks on every one.
- Reads are timed as a round trip.

Against the emulator (start it first with ``uv run just emu-serve``):

    uv run python examples/update_rate.py

A ``socket://`` URL has no baud rate, so for one the demo holds each write for as long
as its bytes would take on a real line (``--no-throttle`` turns that off and shows the
library's own speed). Against a real Sign the serial port sets the pace:

    uv run python examples/update_rate.py /dev/tty.usbserial-1410 --model 4120C

It ERASES EVERY FILE on the Sign: it writes its own Memory Configuration.
"""

import argparse
import time
from collections.abc import Callable
from dataclasses import dataclass

from alpha_led_sign import (
    Color,
    Frame,
    Message,
    Mode,
    Position,
    RunOrder,
    SerialFormat,
    SerialTransport,
    Sign,
    SignModel,
    StringFile,
    StringRef,
    TextFile,
    Transport,
    models,
)
from alpha_led_sign.protocol import Segment, requires

EMULATOR = "socket://127.0.0.1:4120"  # the port `just emu-serve` opens
BOARD, VALUE = "A", "V"
STRING_SIZE = 64
BITS_PER_BYTE = {SerialFormat.EIGHT_N_ONE: 10, SerialFormat.SEVEN_E_TWO: 11}


def can_show(model: SignModel, code: object) -> bool:
    """Whether ``model`` has ``code``, by the same rules ``Sign(strict=True)`` checks."""
    version, capability = requires(code)
    if version > max(model.protocol_versions):
        return False
    return capability is None or model.capabilities is None or capability in model.capabilities


class MeteredTransport:
    """A Transport that counts the bytes written through it.

    With ``seconds_per_byte``, each write also takes as long as its bytes would on a
    real serial line. A ``socket://`` URL has no baud rate of its own, so this is how
    a run against the emulator gets a real line's pace.
    """

    def __init__(self, inner: Transport, seconds_per_byte: float | None = None) -> None:
        self.inner = inner
        self.written = 0
        self.seconds_per_byte = seconds_per_byte
        self._line_free_at = 0.0

    def write(self, data: bytes) -> None:
        self.written += len(data)
        self.inner.write(data)
        if self.seconds_per_byte:
            start = max(time.perf_counter(), self._line_free_at)
            self._line_free_at = start + len(data) * self.seconds_per_byte
            time.sleep(max(0.0, self._line_free_at - time.perf_counter()))

    def pause(self, seconds: float) -> None:
        self.inner.pause(seconds)

    def read(self, timeout: float) -> bytes:
        return self.inner.read(timeout)

    def close(self) -> None:
        self.inner.close()


@dataclass
class Result:
    name: str
    count: int
    seconds: float
    bytes_each: float
    ok: bool
    detail: str

    def row(self, line_bytes_per_second: float) -> str:
        rate = self.count / self.seconds
        ceiling = line_bytes_per_second / self.bytes_each
        verdict = "ok" if self.ok else f"FAILED: {self.detail}"
        return (
            f"{self.name:<26} {rate:>9.1f} {1000 / rate:>8.1f} {self.bytes_each:>7.0f}"
            f" {ceiling:>9.1f}  {verdict}"
        )


def burst(
    meter: MeteredTransport, count: int, push: Callable[[int], object]
) -> tuple[float, float]:
    """Run ``push(0..count-1)`` back to back; return seconds taken and bytes per push."""
    start_bytes = meter.written
    start = time.perf_counter()
    for i in range(count):
        push(i)
    seconds = time.perf_counter() - start
    return seconds, (meter.written - start_bytes) / count


def check_line(sign: Sign) -> tuple[bool, str]:
    errors = sign.serial_errors()  # reading also clears the register
    return errors.ok, "" if errors.ok else str(errors)


def string_burst(sign: Sign, meter: MeteredTransport, count: int, size: int) -> Result:
    def value(i: int) -> str:
        return f"{i:0{size}d}"[-size:]

    seconds, each = burst(meter, count, lambda i: sign.write_string(VALUE, value(i)))
    last = value(count - 1)
    read = sign.read_string(VALUE)
    ok, detail = check_line(sign)
    if read != (last,):
        ok, detail = False, f"read back {read!r}, last sent {last!r}"
    return Result(f"STRING File, {size} chars", count, seconds, each, ok, detail)


def text_burst(sign: Sign, meter: MeteredTransport, count: int, board: Message) -> Result:
    seconds, each = burst(meter, count, lambda i: sign.write_text(BOARD, f"{i:06d}"))
    ok, detail = check_line(sign)
    if sign.read_text(BOARD) != Message(Frame(Mode.HOLD, Position.FILL, f"{count - 1:06d}")):
        ok, detail = False, "the last TEXT File write did not read back"
    sign.write_text(BOARD, board)  # back to the live STRING File
    return Result("TEXT File (blanks)", count, seconds, each, ok, detail)


def read_round_trips(sign: Sign, meter: MeteredTransport, count: int) -> Result:
    seconds, each = burst(meter, count, lambda _i: sign.read_string(VALUE))
    ok, detail = check_line(sign)
    return Result("STRING File read", count, seconds, each, ok, detail)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("url", nargs="?", default=EMULATOR, help=f"default: {EMULATOR}")
    parser.add_argument("--model", default="4120C", help="Sign Model name (default: 4120C)")
    parser.add_argument("--address", type=int, default=1, help="Sign Address (default: 1)")
    parser.add_argument("--baud", type=int, default=9600, help="baud rate (default: 9600)")
    parser.add_argument("--7e2", dest="seven_e_two", action="store_true", help="7E2, not 8N1")
    parser.add_argument("--count", type=int, default=50, help="writes per burst (default: 50)")
    parser.add_argument(
        "--no-throttle",
        action="store_true",
        help="for socket:// URLs, don't hold writes to the baud rate",
    )
    args = parser.parse_args()

    model = models.get(args.model)
    serial_format = SerialFormat.SEVEN_E_TWO if args.seven_e_two else SerialFormat.EIGHT_N_ONE
    line_bytes_per_second = args.baud / BITS_PER_BYTE[serial_format]
    port = SerialTransport(args.url, baudrate=args.baud, serial_format=serial_format)
    throttle = args.url.startswith("socket://") and not args.no_throttle
    meter = MeteredTransport(port, 1 / line_bytes_per_second if throttle else None)

    color: list[Segment] = [Color.GREEN] if can_show(model, Color.GREEN) else []
    board = Message(Frame(Mode.HOLD, Position.FILL, [*color, StringRef(VALUE)]))

    with Sign(meter, model=model, address=args.address, strict=True) as sign:
        print(f"Setting up the {model.name} at {args.url}...")
        if throttle:
            print(f"Writes are held to {args.baud} baud: a socket:// URL has no line speed.")
        sign.configure_memory([TextFile(BOARD, size=64), StringFile(VALUE, size=STRING_SIZE)])
        sign.write_string(VALUE, "")
        sign.write_text(BOARD, board)
        sign.run_sequence(BOARD, order=RunOrder.IN_ORDER)
        check_line(sign)  # start from a clear register

        results = [
            *(string_burst(sign, meter, args.count, size) for size in (4, 16, STRING_SIZE)),
            text_burst(sign, meter, max(args.count // 10, 5), board),
            read_round_trips(sign, meter, max(args.count // 10, 5)),
        ]

    fmt = "7E2" if args.seven_e_two else "8N1"
    print(f"\n{'':<26} {'per s':>9} {'ms each':>8} {'bytes':>7} {'line max':>9}")
    for result in results:
        print(result.row(line_bytes_per_second))
    print(
        f"\n'line max' is the most updates per second a {args.baud} baud {fmt} line can"
        f" carry ({line_bytes_per_second:.0f} bytes/s). A read's bytes count only what was"
        " sent, not the Sign's answer."
    )


if __name__ == "__main__":
    main()
