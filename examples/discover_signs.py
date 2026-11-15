"""Find the Signs on the wire and their Sign Addresses.

Broadcasts a Network Query (p. 32) and lists every Sign that answers: its Sign
Address, Sign Type, the registered Sign Model with that type, and its Serial Error
Status Register. It changes nothing on the Signs.

Each Sign answers 1 s + 0.5 s x its address after the query, so the search waits for
the highest address you ask about: over two minutes for all 255 (the default), about
22 s for ``--max-address 40``. A Sign ignores other commands until it has answered,
so stopping early leaves it deaf for the rest of its wait.

Against the emulator (start it first with ``just emu-serve``):

    uv run python examples/discover_signs.py

Against a real line:

    uv run python examples/discover_signs.py /dev/tty.usbserial-1410

Pass the address it finds to the other examples with ``--address``.
"""

import argparse
import warnings

from alpha_led_sign import SerialFormat, SerialTransport, discover
from alpha_led_sign.discovery import FIRST_ANSWER_DELAY, MARGIN, PER_ADDRESS_DELAY
from alpha_led_sign.protocol.addresses import check_sign_address

EMULATOR = "socket://127.0.0.1:4120"  # the port `just emu-serve` opens


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("url", nargs="?", default=EMULATOR, help=f"default: {EMULATOR}")
    parser.add_argument(
        "--max-address", type=int, default=255, help="highest address to wait for (default: 255)"
    )
    parser.add_argument("--baud", type=int, default=9600, help="baud rate (default: 9600)")
    parser.add_argument("--7e2", dest="seven_e_two", action="store_true", help="7E2, not 8N1")
    parser.add_argument("--no-checksum", action="store_true", help="send the query without one")
    args = parser.parse_args()
    check_sign_address(args.max_address, name="--max-address")

    serial_format = SerialFormat.SEVEN_E_TWO if args.seven_e_two else SerialFormat.EIGHT_N_ONE
    wait = FIRST_ANSWER_DELAY + args.max_address * PER_ADDRESS_DELAY + MARGIN
    print(f"Querying addresses 0-{args.max_address} on {args.url} (about {wait:.0f} s)...")

    with (
        SerialTransport(args.url, baudrate=args.baud, serial_format=serial_format) as port,
        warnings.catch_warnings(record=True) as garbled,
    ):
        warnings.simplefilter("always")
        found = discover(port, max_address=args.max_address, checksum=not args.no_checksum)

    for warning in garbled:
        print(f"warning: {warning.message}")
    if not found:
        print(
            "No Sign answered. Check the cable, the baud rate and serial format, and"
            " raise --max-address if a Sign's address may be higher."
        )
        return

    print(f"\n{'address':>7}  {'type':<4}  {'model':<12}  serial errors")
    for sign in found:
        model = sign.model.name if sign.model else "(unknown)"
        errors = [name for name, set_ in vars(sign.errors).items() if set_] or ["none"]
        print(f"{sign.address:>7}  {sign.sign_type!r:<4}  {model:<12}  {', '.join(errors)}")


if __name__ == "__main__":
    main()
