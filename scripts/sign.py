"""Set up a Sign and read its state from the command line.

    just sign info
    just sign discover --max-address 15
    just sign configure A:text:512 T:string:16 P:picture:5x4 --yes
    just sign clock --format 24
    just sign speaker on
    just sign beep
    just sign tone 100 5 --repeats 2
    just sign address 3
    just sign sequence AB --order in-order
    just sign run-time A 08:00-17:00
    just sign run-days A weekdays
    just sign show "{color red}Hello"
    just sign string T "72F"
    just sign picture P arrow.txt
    just sign priority "{frame flash}EMERGENCY"
    just sign priority --clear
    just sign read A
    just sign read T --string
    just sign read P --picture
    just sign reset
    just sign clear-memory

The port and the other connection settings come from the same ALPHA_SIGN_*
variables as the hardware tests, or from the options. At Sign Address 0 (the
default) reads go to every Sign on the line, so connect only one Sign.
"""

import argparse
import os
import sys
from collections.abc import Callable
from datetime import datetime, time
from enum import Enum
from pathlib import Path

from alpha_led_sign import (
    DotsPicture,
    DotsPictureFile,
    PictureColors,
    RunDay,
    RunDays,
    RunOrder,
    RunTime,
    SerialFormat,
    Sign,
    StringFile,
    TextFile,
    TimeFormat,
    Tone,
    Weekday,
    discover,
    models,
    to_markup,
)
from alpha_led_sign.protocol.memory import MemoryFile

FORMATS = {"8N1": SerialFormat.EIGHT_N_ONE, "7E2": SerialFormat.SEVEN_E_TWO}
COLORS = {
    "mono": PictureColors.MONOCHROME,
    "tri": PictureColors.TRICOLOR,
    "eight": PictureColors.EIGHT_COLOR,
}
TIME_FORMATS = {"12": TimeFormat.AM_PM, "24": TimeFormat.TWENTY_FOUR_HOUR}
TONES = {"beeps": Tone.THREE_BEEPS, "continuous": Tone.CONTINUOUS}
NAMED_RUN_TIMES = {"always": RunTime.ALWAYS, "never": RunTime.NEVER, "all-day": RunTime.ALL_DAY}


def names[E: Enum](enum: type[E]) -> dict[str, E]:
    """An enum's members by their names in lowercase, with hyphens: ``in-order``."""
    return {member.name.lower().replace("_", "-"): member for member in enum}


def memory_file(spec: str) -> MemoryFile:
    """LABEL:text:SIZE, LABEL:string:SIZE, or LABEL:picture:ROWSxCOLS[:mono|tri|eight].
    Add :locked to a TEXT or picture File to lock it against the IR keyboard."""
    try:
        label, kind, size, *rest = spec.split(":")
        locked = "locked" in rest
        rest = [r for r in rest if r != "locked"]
        if kind == "text" and not rest:
            return TextFile(label, size=int(size), locked=locked)
        if kind == "string" and not rest and not locked:
            return StringFile(label, size=int(size))
        if kind == "picture" and len(rest) <= 1:
            rows, columns = (int(n) for n in size.lower().split("x"))
            colors = COLORS[rest[0]] if rest else PictureColors.MONOCHROME
            return DotsPictureFile(label, rows=rows, columns=columns, colors=colors, locked=locked)
    except (ValueError, KeyError) as error:
        raise argparse.ArgumentTypeError(f"{spec!r}: {error}") from None
    raise argparse.ArgumentTypeError(f"{spec!r} is not {memory_file.__doc__}")


def run_time(spec: str) -> RunTime:
    """always, never, all-day, or HH:MM-HH:MM on 10-minute steps."""
    if spec in NAMED_RUN_TIMES:
        return NAMED_RUN_TIMES[spec]
    try:
        start, stop = (time.fromisoformat(t) for t in spec.split("-"))
        return RunTime.between(start, stop)
    except ValueError as error:
        raise argparse.ArgumentTypeError(f"{spec!r}: {error}") from None


def confirm(args: argparse.Namespace, warning: str) -> None:
    if args.yes:
        return
    if input(f"{warning} Go on? [y/N] ").strip().lower() not in ("y", "yes"):
        sys.exit("not changed")


def open_sign(args: argparse.Namespace) -> Sign:
    if not args.port:
        sys.exit("give --port or set ALPHA_SIGN_PORT")
    return Sign.serial(
        args.port,
        model=models.get(args.model),
        baudrate=args.baud,
        serial_format=FORMATS[args.format],
        address=args.address,
        broadcast_reads=args.address == 0,
    )


# Reading


def info(sign: Sign, _: argparse.Namespace) -> None:
    i = sign.info()
    used = i.memory_total - i.memory_free
    print(f"model       {sign.model.name}")
    print(f"firmware    {i.firmware} rev {i.revision} ({i.firmware_date})")
    print(f"clock       {i.time:%H:%M} ({i.time_format.name.lower()})")
    print(f"speaker     {'on' if i.speaker_enabled else 'off'}")
    print(f"memory      {used} of {i.memory_total} bytes used, {i.memory_free} free")
    errors = sign.serial_errors()
    print(f"serial      {'ok' if errors.ok else errors}")


def find(sign: Sign, args: argparse.Namespace) -> None:
    found = discover(sign.transport, max_address=args.max_address)
    for s in found:
        model = s.model.name if s.model else f"Sign Type {s.sign_type!r}"
        print(f"address {s.address:3}  {model}  {'ok' if s.errors.ok else s.errors}")
    if not found:
        print("no Sign answered")


def read(sign: Sign, args: argparse.Namespace) -> None:
    if args.picture:
        picture = sign.read_dots_picture(args.label)
        print(f"{picture.height} x {picture.width}")
        for row in picture.rows:
            print("".join(pixel.value for pixel in row))
    elif args.string:
        print(to_markup(sign.read_string(args.label)))
    else:
        print(to_markup(sign.read_text(args.label)))


# Setup


def configure(sign: Sign, args: argparse.Namespace) -> None:
    confirm(args, "This erases every File on the Sign.")
    sign.configure_memory(args.files)
    print("configured:", ", ".join(f"{f.label} ({type(f).__name__})" for f in args.files))


def clear_memory(sign: Sign, args: argparse.Namespace) -> None:
    confirm(args, "This erases every File and the Memory Configuration.")
    sign.clear_memory()


def reset(sign: Sign, _: argparse.Namespace) -> None:
    sign.soft_reset()


def clock(sign: Sign, args: argparse.Namespace) -> None:
    now = datetime.now()
    sign.set_clock(now)
    if args.time_format:
        sign.set_time_format(TIME_FORMATS[args.time_format])
    print(f"clock set to {now:%Y-%m-%d %H:%M}")


def speaker(sign: Sign, args: argparse.Namespace) -> None:
    sign.set_speaker(args.state == "on")


def beep(sign: Sign, args: argparse.Namespace) -> None:
    sign.beep(TONES[args.tone])


def tone(sign: Sign, args: argparse.Namespace) -> None:
    sign.tone(args.frequency, args.duration, args.repeats)


def address(sign: Sign, args: argparse.Namespace) -> None:
    sign.set_sign_address(args.new, broadcast=args.broadcast)
    print(f"Sign Address is now {args.new}; pass --address {args.new} from now on")


# Scheduling


def sequence(sign: Sign, args: argparse.Namespace) -> None:
    sign.run_sequence(args.labels, order=names(RunOrder)[args.order], locked=args.locked)


def set_run_time(sign: Sign, args: argparse.Namespace) -> None:
    sign.set_run_times({args.label: args.when})


def set_run_days(sign: Sign, args: argparse.Namespace) -> None:
    days = RunDays(names(RunDay)[args.start], names(Weekday)[args.stop])
    sign.set_run_days({args.label: days})


# Content


def show(sign: Sign, args: argparse.Namespace) -> None:
    sign.write_text(args.label, args.markup)


def string(sign: Sign, args: argparse.Namespace) -> None:
    sign.write_string(args.label, args.markup)


def picture(sign: Sign, args: argparse.Namespace) -> None:
    text = sys.stdin.read() if args.file == "-" else Path(args.file).read_text()
    pic = DotsPicture.parse(text)
    sign.write_dots_picture(args.label, pic)
    print(f"wrote a {pic.height} x {pic.width} picture to {args.label}")


def priority(sign: Sign, args: argparse.Namespace) -> None:
    if args.clear:
        sign.clear_priority()
    elif args.markup is None:
        sys.exit("give markup to show, or --clear")
    else:
        sign.priority(args.markup)


def main() -> None:
    env = os.environ
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--port", default=env.get("ALPHA_SIGN_PORT"), help="serial port or pyserial URL"
    )
    parser.add_argument(
        "--model", default=env.get("ALPHA_SIGN_MODEL", "4120C"), choices=models.REGISTRY
    )
    parser.add_argument("--address", type=int, default=int(env.get("ALPHA_SIGN_ADDRESS", "0")))
    parser.add_argument("--baud", type=int, default=int(env.get("ALPHA_SIGN_BAUD", "9600")))
    parser.add_argument("--format", default=env.get("ALPHA_SIGN_FORMAT", "8N1"), choices=FORMATS)
    commands = parser.add_subparsers(required=True, metavar="command")

    def command(
        name: str, run: Callable[[Sign, argparse.Namespace], None], summary: str
    ) -> argparse.ArgumentParser:
        p = commands.add_parser(name, help=summary, description=summary)
        p.set_defaults(run=run)
        return p

    command("info", info, "firmware, clock, speaker, memory, serial errors")

    p = command("discover", find, "list the Signs on the line and their Sign Addresses")
    p.add_argument("--max-address", type=int, default=15, help="highest address to wait for")

    p = command("read", read, "read a File back (TEXT unless told otherwise)")
    p.add_argument("label")
    kind = p.add_mutually_exclusive_group()
    kind.add_argument("--string", action="store_true", help="a STRING File")
    kind.add_argument("--picture", action="store_true", help="a DOTS PICTURE File")

    p = command("configure", configure, "replace the Memory Configuration (erases every File)")
    p.add_argument("files", nargs="+", type=memory_file, help=memory_file.__doc__)
    p.add_argument("--yes", action="store_true", help="don't ask before erasing")

    p = command("clear-memory", clear_memory, "erase every File and the Memory Configuration")
    p.add_argument("--yes", action="store_true", help="don't ask before erasing")

    command("reset", reset, "restart the Sign; memory is kept")

    p = command("clock", clock, "set the Sign's clock to this computer's")
    p.add_argument("--format", dest="time_format", choices=TIME_FORMATS, help="12 or 24 hour")

    p = command("speaker", speaker, "turn the speaker on or off (tones need it on)")
    p.add_argument("state", choices=["on", "off"])

    p = command("beep", beep, "sound a built-in tone")
    p.add_argument("tone", nargs="?", default="beeps", choices=TONES)

    p = command("tone", tone, "play a programmable tone")
    p.add_argument("frequency", type=int, help="0-254")
    p.add_argument("duration", type=int, help="1-15 tenths of a second")
    p.add_argument("--repeats", type=int, default=0)

    p = command("address", address, "give the Sign a new Sign Address")
    p.add_argument("new", type=int, help="1-255")
    p.add_argument(
        "--broadcast", action="store_true", help="allowed at --address 0: readdresses every Sign"
    )

    p = command("sequence", sequence, "set which TEXT Files run, in order")
    p.add_argument("labels", help="File Labels, such as AB")
    p.add_argument("--order", default="by-run-time", choices=names(RunOrder))
    p.add_argument("--locked", action="store_true", help="lock against the IR keyboard")

    p = command("run-time", set_run_time, "set when a TEXT File runs each day")
    p.add_argument("label")
    p.add_argument("when", type=run_time, help=run_time.__doc__)

    p = command("run-days", set_run_days, "set the days a TEXT File runs")
    p.add_argument("label")
    p.add_argument("start", choices=names(RunDay))
    p.add_argument(
        "--stop", default="sunday", choices=names(Weekday), help="last day, after a single day"
    )

    p = command("show", show, "write markup to a TEXT File")
    p.add_argument("markup")
    p.add_argument("--label", default="A")

    p = command("string", string, "write markup to a STRING File")
    p.add_argument("label")
    p.add_argument("markup")

    p = command("picture", picture, "write a DOTS PICTURE File from pixel codes 0-8")
    p.add_argument("label")
    p.add_argument("file", help="one row of pixel codes per line, or - for stdin")

    p = command("priority", priority, "show markup over everything, or end it")
    p.add_argument("markup", nargs="?")
    p.add_argument("--clear", action="store_true")

    args = parser.parse_args()
    with open_sign(args) as sign:
        args.run(sign, args)


if __name__ == "__main__":
    main()
