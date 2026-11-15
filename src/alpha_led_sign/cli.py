"""The ``alpha-led-sign`` command: set up a Sign and read its state from the command line.

Needs the ``cli`` extra (``pip install 'alpha-led-sign[cli]'``)::

    alpha-led-sign --port /dev/tty.usbserial-1410 info
    alpha-led-sign configure A:text:512 T:string:16 P:picture:5x4 --yes
    alpha-led-sign show "{color red}Hello"
    alpha-led-sign read A

The port and the other connection settings come from the options, or from
``ALPHA_SIGN_PORT``, ``ALPHA_SIGN_MODEL``, ``ALPHA_SIGN_ADDRESS``,
``ALPHA_SIGN_BAUD``, and ``ALPHA_SIGN_FORMAT``. At Sign Address 0 (the default)
reads go to every Sign on the line, so connect only one Sign.
"""

import sys
from collections.abc import Callable, Generator, Iterable
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, time
from enum import Enum
from typing import Annotated

try:
    import typer
    from rich.console import Console
    from rich.markup import escape
    from rich.table import Table
except ImportError:  # pragma: no cover - only without the extra
    sys.exit("alpha-led-sign needs its command-line extra: pip install 'alpha-led-sign[cli]'")

import serial

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

_FORMATS = {"8N1": SerialFormat.EIGHT_N_ONE, "7E2": SerialFormat.SEVEN_E_TWO}
_COLORS = {
    "mono": PictureColors.MONOCHROME,
    "tri": PictureColors.TRICOLOR,
    "eight": PictureColors.EIGHT_COLOR,
}
_TIME_FORMATS = {"12": TimeFormat.AM_PM, "24": TimeFormat.TWENTY_FOUR_HOUR}
_TONES = {"beeps": Tone.THREE_BEEPS, "continuous": Tone.CONTINUOUS}
_NAMED_RUN_TIMES = {"always": RunTime.ALWAYS, "never": RunTime.NEVER, "all-day": RunTime.ALL_DAY}
_MEMORY_FILE_HELP = (
    "LABEL:text:SIZE, LABEL:string:SIZE, or LABEL:picture:ROWSxCOLS, with :mono, :tri,"
    " or :eight after a picture for its colors. Add :locked to a TEXT or picture File"
    " to lock it against the IR keyboard."
)
_RUN_TIME_HELP = "always, never, all-day, or HH:MM-HH:MM on 10-minute steps."


def _names[E: Enum](enum: type[E]) -> dict[str, E]:
    """An enum's members by their names in lowercase, with hyphens: ``in-order``.

    Returns:
        The members, keyed by name.
    """
    return {member.name.lower().replace("_", "-"): member for member in enum}


def _one_of(names: Iterable[str]) -> Callable[[str | None], str | None]:
    """A Typer callback that accepts only ``names`` (or no value).

    Returns:
        The callback.
    """
    allowed = list(names)

    def check(value: str | None) -> str | None:
        if value is not None and value not in allowed:
            raise typer.BadParameter(f"{value!r} is not one of {', '.join(allowed)}")
        return value

    return check


def _shown(names: Iterable[str]) -> str:
    """The metavar that lists ``names`` in the help.

    Returns:
        ``[a|b|c]``.
    """
    return "[" + "|".join(names) + "]"


def _memory_file(spec: str) -> MemoryFile:
    """Parse a Memory Configuration entry; the format is ``_MEMORY_FILE_HELP``.

    Returns:
        The File to configure.

    Raises:
        typer.BadParameter: ``spec`` is not in the format.
    """
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
            colors = _COLORS[rest[0]] if rest else PictureColors.MONOCHROME
            return DotsPictureFile(label, rows=rows, columns=columns, colors=colors, locked=locked)
    except (ValueError, KeyError) as error:
        raise typer.BadParameter(f"{spec!r}: {error}") from None
    raise typer.BadParameter(f"{spec!r} is not {_MEMORY_FILE_HELP}")


def _run_time(spec: str) -> RunTime:
    """Parse a run time; the format is ``_RUN_TIME_HELP``.

    Returns:
        The run time.

    Raises:
        typer.BadParameter: ``spec`` is not in the format.
    """
    if spec in _NAMED_RUN_TIMES:
        return _NAMED_RUN_TIMES[spec]
    try:
        start, stop = (time.fromisoformat(t) for t in spec.split("-"))
        return RunTime.between(start, stop)
    except ValueError as error:
        raise typer.BadParameter(f"{spec!r}: {error}") from None


@dataclass(frozen=True)
class _Connection:
    port: str | None
    model: str
    address: int
    baud: int
    serial_format: str


_console = Console()
_errors = Console(stderr=True)

app = typer.Typer(
    name="alpha-led-sign",
    help="Set up an Alpha-protocol LED sign and read its state.",
    no_args_is_help=True,
    pretty_exceptions_enable=False,
)


@app.callback()
def _connect(
    ctx: typer.Context,
    port: Annotated[
        str | None,
        typer.Option(envvar="ALPHA_SIGN_PORT", help="Serial port or pyserial URL."),
    ] = None,
    model: Annotated[
        str,
        typer.Option(
            envvar="ALPHA_SIGN_MODEL",
            callback=_one_of(models.REGISTRY),
            metavar=_shown(models.REGISTRY),
            help="Sign Model.",
        ),
    ] = "4120C",
    address: Annotated[
        int, typer.Option(envvar="ALPHA_SIGN_ADDRESS", help="Sign Address; 0 reaches every Sign.")
    ] = 0,
    baud: Annotated[int, typer.Option(envvar="ALPHA_SIGN_BAUD", help="Line speed.")] = 9600,
    serial_format: Annotated[
        str,
        typer.Option(
            "--format",
            envvar="ALPHA_SIGN_FORMAT",
            callback=_one_of(_FORMATS),
            metavar=_shown(_FORMATS),
            help="Data bits, parity, and stop bits.",
        ),
    ] = "8N1",
) -> None:
    ctx.obj = _Connection(port, model, address, baud, serial_format)


@contextmanager
def _sign(ctx: typer.Context) -> Generator[Sign]:
    """Open the Sign the options name, and report the library's errors without a traceback.

    Yields:
        The open Sign, closed on the way out.

    Raises:
        typer.BadParameter: No port was given.
        typer.Exit: The port failed, or the Sign refused or didn't answer.
    """
    connection: _Connection = ctx.obj
    if not connection.port:
        raise typer.BadParameter("give --port or set ALPHA_SIGN_PORT", param_hint="--port")
    try:
        with Sign.serial(
            connection.port,
            model=models.get(connection.model),
            baudrate=connection.baud,
            serial_format=_FORMATS[connection.serial_format],
            address=connection.address,
            broadcast_reads=connection.address == 0,
        ) as sign:
            yield sign
    except (ValueError, TimeoutError, serial.SerialException) as error:
        _errors.print(f"[red]error:[/red] {escape(str(error))}", highlight=False)
        raise typer.Exit(1) from None


def _confirm(yes: bool, warning: str) -> None:
    """Ask before something that erases Files, unless ``yes``.

    Raises:
        typer.Exit: The person said no.
    """
    if not yes and not typer.confirm(f"{warning} Go on?"):
        _errors.print("not changed")
        raise typer.Exit(1)


_Yes = Annotated[bool, typer.Option("--yes", "-y", help="Don't ask before erasing.")]
_Label = Annotated[str, typer.Argument(help="File Label.")]


# Reading


@app.command("info", help="Firmware, clock, speaker, memory, and serial errors.")
def _info(ctx: typer.Context) -> None:
    with _sign(ctx) as sign:
        i = sign.info()
        errors = sign.serial_errors()
    used = i.memory_total - i.memory_free
    table = Table.grid(padding=(0, 2))
    table.add_row("model", sign.model.name)
    table.add_row("firmware", f"{i.firmware} rev {i.revision} ({i.firmware_date})")
    table.add_row("clock", f"{i.time:%H:%M} ({i.time_format.name.lower()})")
    table.add_row("speaker", "on" if i.speaker_enabled else "off")
    table.add_row("memory", f"{used} of {i.memory_total} bytes used, {i.memory_free} free")
    table.add_row("serial", "ok" if errors.ok else str(errors))
    _console.print(table, highlight=False)


@app.command("discover", help="List the Signs on the line and their Sign Addresses.")
def _discover(
    ctx: typer.Context,
    max_address: Annotated[int, typer.Option(help="Highest address to wait for.")] = 15,
) -> None:
    with _sign(ctx) as sign:
        found = discover(sign.transport, max_address=max_address)
    if not found:
        _console.print("no Sign answered")
        return
    table = Table("address", "Sign Model", "serial")
    for s in found:
        model = s.model.name if s.model else f"Sign Type {s.sign_type!r}"
        table.add_row(str(s.address), model, "ok" if s.errors.ok else str(s.errors))
    _console.print(table, highlight=False)


@app.command("read", help="Read a File back: TEXT as markup unless told otherwise.")
def _read(
    ctx: typer.Context,
    label: _Label,
    string: Annotated[bool, typer.Option("--string", help="A STRING File.")] = False,
    picture: Annotated[bool, typer.Option("--picture", help="A DOTS PICTURE File.")] = False,
) -> None:
    if string and picture:
        raise typer.BadParameter("give --string or --picture, not both")
    with _sign(ctx) as sign:
        if picture:
            dots = sign.read_dots_picture(label)
            typer.echo(f"{dots.height} x {dots.width}")
            for row in dots.rows:
                typer.echo("".join(pixel.value for pixel in row))
        elif string:
            typer.echo(to_markup(sign.read_string(label)))
        else:
            typer.echo(to_markup(sign.read_text(label)))


# Setup


@app.command("configure", help="Replace the Memory Configuration. Erases every File.")
def _configure(
    ctx: typer.Context,
    files: Annotated[list[str], typer.Argument(help=_MEMORY_FILE_HELP)],
    yes: _Yes = False,
) -> None:
    memory = [_memory_file(spec) for spec in files]
    _confirm(yes, "This erases every File on the Sign.")
    with _sign(ctx) as sign:
        sign.configure_memory(memory)
    typer.echo("configured: " + ", ".join(f"{f.label} ({type(f).__name__})" for f in memory))


@app.command("clear-memory", help="Erase every File and the Memory Configuration.")
def _clear_memory(ctx: typer.Context, yes: _Yes = False) -> None:
    _confirm(yes, "This erases every File and the Memory Configuration.")
    with _sign(ctx) as sign:
        sign.clear_memory()


@app.command("reset", help="Restart the Sign; memory is kept.")
def _reset(ctx: typer.Context) -> None:
    with _sign(ctx) as sign:
        sign.soft_reset()


@app.command("clock", help="Set the Sign's clock to this computer's.")
def _clock(
    ctx: typer.Context,
    time_format: Annotated[
        str | None,
        typer.Option(
            "--format",
            callback=_one_of(_TIME_FORMATS),
            metavar=_shown(_TIME_FORMATS),
            help="12 or 24 hour.",
        ),
    ] = None,
) -> None:
    now = datetime.now()
    with _sign(ctx) as sign:
        sign.set_clock(now)
        if time_format:
            sign.set_time_format(_TIME_FORMATS[time_format])
    typer.echo(f"clock set to {now:%Y-%m-%d %H:%M}")


@app.command("speaker", help="Turn the speaker on or off; tones need it on.")
def _speaker(
    ctx: typer.Context,
    state: Annotated[
        str,
        typer.Argument(
            callback=_one_of(["on", "off"]), help="One of: " + ", ".join(["on", "off"]) + "."
        ),
    ],
) -> None:
    with _sign(ctx) as sign:
        sign.set_speaker(state == "on")


@app.command("beep", help="Sound a built-in tone.")
def _beep(
    ctx: typer.Context,
    tone: Annotated[
        str, typer.Argument(callback=_one_of(_TONES), help="One of: " + ", ".join(_TONES) + ".")
    ] = "beeps",
) -> None:
    with _sign(ctx) as sign:
        sign.beep(_TONES[tone])


@app.command("tone", help="Play a programmable tone.")
def _tone(
    ctx: typer.Context,
    frequency: Annotated[int, typer.Argument(help="0-254.")],
    duration: Annotated[int, typer.Argument(help="1-15 tenths of a second.")],
    repeats: Annotated[int, typer.Option(help="Plays after the first.")] = 0,
) -> None:
    with _sign(ctx) as sign:
        sign.tone(frequency, duration, repeats)


@app.command("address", help="Give the Sign a new Sign Address.")
def _address(
    ctx: typer.Context,
    new: Annotated[int, typer.Argument(help="1-255.")],
    broadcast: Annotated[
        bool, typer.Option(help="Allowed at --address 0: readdresses every Sign.")
    ] = False,
) -> None:
    with _sign(ctx) as sign:
        sign.set_sign_address(new, broadcast=broadcast)
    typer.echo(f"Sign Address is now {new}; pass --address {new} from now on")


# Scheduling


@app.command("sequence", help="Set which TEXT Files run, in order.")
def _sequence(
    ctx: typer.Context,
    labels: Annotated[str, typer.Argument(help="File Labels, such as AB.")],
    order: Annotated[
        str, typer.Option(callback=_one_of(_names(RunOrder)), metavar=_shown(_names(RunOrder)))
    ] = "by-run-time",
    locked: Annotated[bool, typer.Option(help="Lock against the IR keyboard.")] = False,
) -> None:
    with _sign(ctx) as sign:
        sign.run_sequence(labels, order=_names(RunOrder)[order], locked=locked)


@app.command("run-time", help="Set when a TEXT File runs each day.")
def _set_run_time(
    ctx: typer.Context,
    label: _Label,
    when: Annotated[str, typer.Argument(help=_RUN_TIME_HELP)],
) -> None:
    run_time = _run_time(when)
    with _sign(ctx) as sign:
        sign.set_run_times({label: run_time})


@app.command("run-days", help="Set the days a TEXT File runs.")
def _set_run_days(
    ctx: typer.Context,
    label: _Label,
    start: Annotated[
        str,
        typer.Argument(
            callback=_one_of(_names(RunDay)), help="One of: " + ", ".join(_names(RunDay)) + "."
        ),
    ],
    stop: Annotated[
        str,
        typer.Option(
            callback=_one_of(_names(Weekday)),
            metavar=_shown(_names(Weekday)),
            help="Last day, after a single day.",
        ),
    ] = "sunday",
) -> None:
    days = RunDays(_names(RunDay)[start], _names(Weekday)[stop])
    with _sign(ctx) as sign:
        sign.set_run_days({label: days})


# Content


@app.command("show", help="Write markup to a TEXT File.")
def _show(
    ctx: typer.Context,
    markup: Annotated[str, typer.Argument(help="Markup, such as '{color red}Hello'.")],
    label: Annotated[str, typer.Option(help="File Label.")] = "A",
) -> None:
    with _sign(ctx) as sign:
        sign.write_text(label, markup)


@app.command("string", help="Write markup to a STRING File.")
def _string(ctx: typer.Context, label: _Label, markup: str) -> None:
    with _sign(ctx) as sign:
        sign.write_string(label, markup)


@app.command("picture", help="Write a DOTS PICTURE File from pixel codes 0-8.")
def _picture(
    ctx: typer.Context,
    label: _Label,
    file: Annotated[
        typer.FileText, typer.Argument(help="One row of pixel codes per line, or - for stdin.")
    ],
) -> None:
    dots = DotsPicture.parse(file.read())
    with _sign(ctx) as sign:
        sign.write_dots_picture(label, dots)
    typer.echo(f"wrote a {dots.height} x {dots.width} picture to {label}")


@app.command("priority", help="Show markup over everything, or end it with --clear.")
def _priority(
    ctx: typer.Context,
    markup: Annotated[str | None, typer.Argument()] = None,
    clear: Annotated[bool, typer.Option("--clear", help="End the priority message.")] = False,
) -> None:
    if clear:
        with _sign(ctx) as sign:
            sign.clear_priority()
    elif markup is None:
        raise typer.BadParameter("give markup to show, or --clear")
    else:
        with _sign(ctx) as sign:
            sign.priority(markup)
