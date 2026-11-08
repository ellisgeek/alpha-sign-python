"""Vegas mode: a light show of everything the Sign can do.

Mixing consoles from Digidesign (later Avid) have a "Vegas mode": a factory service
test that runs every fader, LED strip, and display through a flashy cascade, which
live-sound engineers took up as a show of its own. This is the same idea for an Alpha
Sign. It cascades through every color, Mode, font, Special Mode, and Special Graphic
the Sign Model has, both lines, and a flashing Priority TEXT File with a tone sweep,
and loops until you press Ctrl-C. Content the model lacks is left out, so it runs on
any Sign Model.

Against the emulator (start it first with ``uv run just emu-serve``):

    uv run python examples/vegas_mode.py

Against a real Sign:

    uv run python examples/vegas_mode.py /dev/tty.usbserial-1410 --model 4120C

It ERASES EVERY FILE on the Sign: the show writes its own Memory Configuration.
"""

import argparse
import itertools
import time
from datetime import datetime

from alpha_led_sign import (
    CharacterFlash,
    Color,
    CurrentDate,
    CurrentTime,
    DateFormat,
    Font,
    Frame,
    Message,
    Mode,
    Position,
    RunOrder,
    Sign,
    SignModel,
    SpecialGraphic,
    SpecialMode,
    TextFile,
    TimeFormat,
    models,
)
from alpha_led_sign.protocol import Segment, requires

EMULATOR = "socket://127.0.0.1:4120"  # the port `just emu-serve` opens

SWEEPS, MODES, FONTS, SPECIALS, LINES = "ABCDE"
RAINBOW = [Color.RED, Color.ORANGE, Color.YELLOW, Color.GREEN, Color.AMBER]
WIPES = [Mode.WIPE_RIGHT, Mode.WIPE_DOWN, Mode.WIPE_LEFT, Mode.WIPE_UP]


def can_show(model: SignModel, code: object) -> bool:
    """Whether ``model`` has ``code``, by the same rules ``Sign(strict=True)`` checks."""
    version, capability = requires(code)
    if version > max(model.protocol_versions):
        return False
    return capability is None or model.capabilities is None or capability in model.capabilities


class Paint:
    """Color Control Codes for a model. A red-only Sign takes none at all."""

    def __init__(self, model: SignModel) -> None:
        self.colors = [color for color in Color if can_show(model, color)]
        self.rainbow = [color for color in RAINBOW if color in self.colors]
        self._next = itertools.cycle(self.colors or [Color.RED])

    def next(self) -> list[Segment]:
        """The next color in turn, as segments to put before some text."""
        return [next(self._next)] if self.colors else []

    def rainbow_text(self, text: str) -> list[Segment]:
        """Each letter in the next rainbow color."""
        if not self.rainbow:
            return [text]
        segments: list[Segment] = []
        for letter, color in zip(text, itertools.cycle(self.rainbow), strict=False):
            segments += [color, letter]
        return segments


def name(code: Mode | SpecialMode | SpecialGraphic | Font) -> str:
    return code.name.replace("_", " ")


def sweeps(model: SignModel, paint: Paint) -> Message:
    """Bars of light wiped across the panel in each direction, in each color."""
    bar = "#" * ((model.columns or 120) // 6)
    font: list[Segment] = [Font.FULL_HEIGHT] if can_show(model, Font.FULL_HEIGHT) else []
    return Message(
        Frame(Mode.HOLD, Position.FILL, paint.rainbow_text("VEGAS MODE")),
        Frame(Mode.HOLD, Position.FILL, [*paint.next(), model.name]),
        *(
            Frame(wipe, Position.FILL, [*font, *paint.next(), bar])
            for wipe in itertools.islice(itertools.cycle(WIPES), max(8, len(paint.colors)))
        ),
    )


def mode_cascade(model: SignModel, paint: Paint) -> Message:
    return Message(
        *(
            Frame(mode, Position.FILL, [*paint.next(), name(mode)])
            for mode in Mode
            if can_show(model, mode)
        )
    )


def font_cascade(model: SignModel, paint: Paint) -> Message:
    return Message(
        *(
            Frame(Mode.ROLL_LEFT, Position.FILL, [font, *paint.next(), name(font)])
            for font in Font
            if can_show(model, font)
        )
    )


def special_effects(model: SignModel, paint: Paint) -> Message:
    effects = [
        Frame(mode, Position.FILL, [*paint.next(), name(mode)])
        for mode in SpecialMode
        if can_show(model, mode)
    ]
    graphics = [Frame(graphic) for graphic in SpecialGraphic if can_show(model, graphic)]
    # Alternate effects and graphics. A graphic Frame can't hold text, so it stands alone.
    paired = itertools.chain.from_iterable(itertools.zip_longest(effects, graphics))
    return Message(*(frame for frame in paired if frame is not None))


def two_lines(model: SignModel, paint: Paint) -> Message:
    if (model.lines or 1) < 2:
        return Message(Frame(Mode.HOLD, Position.FILL, [*paint.next(), CurrentTime()]))
    return Message(
        Frame(Mode.ROLL_DOWN, Position.TOP, paint.rainbow_text("TOP LINE")),
        Frame(Mode.ROLL_UP, Position.BOTTOM, [*paint.next(), CurrentDate(DateFormat.MMM_DD_YYYY)]),
        Frame(Mode.WIPE_LEFT, Position.TOP, [*paint.next(), CurrentTime()]),
        Frame(Mode.WIPE_RIGHT, Position.BOTTOM, paint.rainbow_text("BOTTOM LINE")),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("url", nargs="?", default=EMULATOR, help=f"default: {EMULATOR}")
    parser.add_argument("--model", default="4120C", help="Sign Model name (default: 4120C)")
    parser.add_argument("--address", type=int, default=1, help="Sign Address (default: 1)")
    parser.add_argument("--pace", type=float, default=2.5, help="seconds per Frame (default: 2.5)")
    parser.add_argument("--quiet", action="store_true", help="no tones")
    parser.add_argument("--once", action="store_true", help="one lap, then stop")
    args = parser.parse_args()

    model = models.get(args.model)
    paint = Paint(model)
    acts = {
        SWEEPS: sweeps(model, paint),
        MODES: mode_cascade(model, paint),
        FONTS: font_cascade(model, paint),
        SPECIALS: special_effects(model, paint),
        LINES: two_lines(model, paint),
    }
    finale = Frame(Mode.FLASH, Position.FILL, [CharacterFlash(), *paint.rainbow_text("ALPHA")])

    # strict: anything this model can't show raises before it is sent.
    with Sign.serial(args.url, model=model, address=args.address, strict=True) as sign:
        print(f"Setting up the {model.name}...")
        sign.configure_memory([TextFile(label, size=1024) for label in acts])
        sign.set_clock(datetime.now())
        sign.set_time_format(TimeFormat.AM_PM)
        sign.set_speaker(not args.quiet)
        for label, message in acts.items():
            sign.write_text(label, message)

        print("Running. Ctrl-C to stop.")
        try:
            for lap in itertools.count(1):
                print(f"\nLap {lap}")
                for label, message in acts.items():
                    sign.run_sequence(label, order=RunOrder.IN_ORDER)
                    print(f"  TEXT File {label}: {len(message.frames)} Frames")
                    time.sleep(args.pace * len(message.frames))

                # The Priority TEXT File takes over the display until it is cleared.
                print("  Priority TEXT File")
                sign.priority(finale)
                if not args.quiet:
                    for frequency in range(40, 255, 40):
                        sign.tone(frequency, duration=1)  # waits while the tone plays
                    sign.beep()
                time.sleep(args.pace * 2)
                sign.clear_priority()

                if args.once:
                    break
        except KeyboardInterrupt:
            pass

        # Leave the whole show running on the Sign by itself.
        sign.run_sequence(list(acts), order=RunOrder.IN_ORDER)
        print("\nThe show keeps running on the Sign.")


if __name__ == "__main__":
    main()
