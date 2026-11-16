"""Smoke tests against a real Sign. Opt-in: they never run against a real Sign in CI.

    just test-hardware /dev/tty.usbserial-1410

The same tests run against the emulator (Node and ``npm ci`` in emulator/), which
needs no settings. Erase and re-address tests run there without their opt-in flags:

    just test-emulator

Optional settings:

- ALPHA_SIGN_MODEL: a registered Sign Model name (default 4120C).
- ALPHA_SIGN_ADDRESS: the Sign Address (default 0).
- ALPHA_SIGN_BAUD: baud rate (default 9600).
- ALPHA_SIGN_FORMAT: 8N1 (default) or 7E2.
- ALPHA_SIGN_ALLOW_ERASE=1: also run tests that write the Memory Configuration,
  which ERASES EVERY FILE on the Sign.
- ALPHA_SIGN_ALLOW_READDRESS=1: also capture a Network Query answer at a second Sign
  Address. The test changes the Sign Address, then sets it back. It needs
  ALPHA_SIGN_ADDRESS to be the Sign's real address (not 0).
- ALPHA_SIGN_CAPTURE=<path>: write every byte written and read, with the model,
  firmware, and date, to a JSON file. These captures are test vectors.
- ALPHA_SIGN_WITNESS=1: also run the witnessed tests, which ask you what the Sign
  showed or played. They read your answers, so they run with ``-s``:

      just test-witness /dev/tty.usbserial-1410

Some tests only record what the Sign did and print it; pytest hides that unless you
add ``-rP`` (or ``-s``).

Each test maps to an item on the hardware checklist in docs/spec.md. Record the
results in docs/hardware-results.md.
"""

import json
import os
import warnings
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import ClassVar

import pytest

from alpha_led_sign import (
    Color,
    Control,
    CurrentDate,
    DateFormat,
    DotsPicture,
    DotsPictureFile,
    DotsPictureRef,
    DoubleHigh,
    Font,
    Frame,
    Message,
    Mode,
    PictureColors,
    Position,
    SerialFormat,
    SerialTransport,
    Sign,
    SignModel,
    SpecialMode,
    StringFile,
    StringRef,
    TextFile,
    discover,
    models,
)
from alpha_led_sign.models import UnsupportedCapabilityWarning
from alpha_led_sign.protocol.commands import (
    Command,
    Pause,
    Tone,
    WriteDotsPicture,
)
from alpha_led_sign.protocol.memory import MemoryFile
from alpha_led_sign.protocol.message import Segment
from alpha_led_sign.protocol.requirements import Capability
from tests import emulator
from tests.conftest import EMULATED_SIGN
from tests.recording import RecordingTransport

pytestmark = [pytest.mark.hardware, pytest.mark.emulator]


def _flag(name: str) -> bool:
    return os.environ.get(name) == "1"


@dataclass(frozen=True)
class Settings:
    """How to reach the Sign, from the ALPHA_SIGN_* environment variables."""

    port: str | None
    model: SignModel
    address: int
    baudrate: int
    serial_format: SerialFormat

    @classmethod
    def from_env(cls) -> "Settings":
        env = dict(os.environ)
        if EMULATED:
            # The emulator fixture sets ALPHA_SIGN_PORT and powers up EMULATED_SIGN.
            env |= {
                "ALPHA_SIGN_MODEL": EMULATED_SIGN.model,
                "ALPHA_SIGN_ADDRESS": str(EMULATED_SIGN.sign_address),
            }
            env |= {"ALPHA_SIGN_BAUD": "9600", "ALPHA_SIGN_FORMAT": "8N1"}
        formats = {"8N1": SerialFormat.EIGHT_N_ONE, "7E2": SerialFormat.SEVEN_E_TWO}
        return cls(
            port=env.get("ALPHA_SIGN_PORT"),
            model=models.get(env.get("ALPHA_SIGN_MODEL", "4120C")),
            address=int(env.get("ALPHA_SIGN_ADDRESS", "0")),
            baudrate=int(env.get("ALPHA_SIGN_BAUD", "9600")),
            serial_format=formats[env.get("ALPHA_SIGN_FORMAT", "8N1")],
        )


# True for `-m emulator` (tests/conftest.py sets it before this module is collected).
EMULATED = emulator.selected
SETTINGS = Settings.from_env()
CAPTURE_PATH = os.environ.get("ALPHA_SIGN_CAPTURE")

needs_erase = pytest.mark.skipif(
    not EMULATED and not _flag("ALPHA_SIGN_ALLOW_ERASE"), reason="set ALPHA_SIGN_ALLOW_ERASE=1"
)
needs_readdress = pytest.mark.skipif(
    not EMULATED and (not _flag("ALPHA_SIGN_ALLOW_READDRESS") or SETTINGS.address == 0),
    reason="set ALPHA_SIGN_ALLOW_READDRESS=1 and ALPHA_SIGN_ADDRESS to the Sign's address",
)
needs_witness = (
    pytest.mark.skip(reason="witnessed tests need a person watching a real Sign, not the emulator")
    if EMULATED
    else pytest.mark.skipif(not _flag("ALPHA_SIGN_WITNESS"), reason="set ALPHA_SIGN_WITNESS=1")
)


@dataclass
class Captures:
    """What a hardware session sent and received, per test."""

    recordings: dict[str, list[RecordingTransport]] = field(default_factory=dict)
    firmware: str | None = None

    def write(self, path: Path) -> None:
        path.write_text(
            json.dumps(
                {
                    "model": SETTINGS.model.name,
                    "firmware": self.firmware,
                    "date": date.today().isoformat(),
                    "address": SETTINGS.address,
                    "baudrate": SETTINGS.baudrate,
                    "serial_format": SETTINGS.serial_format.name,
                    "tests": {
                        test: [recording.to_json() for recording in recordings]
                        for test, recordings in self.recordings.items()
                    },
                },
                indent=2,
            )
            + "\n"
        )


@pytest.fixture(scope="session")
def captures() -> Iterator[Captures]:
    found = Captures()
    yield found
    if CAPTURE_PATH and found.recordings:
        found.write(Path(CAPTURE_PATH))


@pytest.fixture
def open_sign(request: pytest.FixtureRequest, captures: Captures) -> Iterator[Callable[[], Sign]]:
    """Open the Sign from the settings, recording its traffic under this test's name."""
    if EMULATED:
        request.getfixturevalue("emulated_sign")
    port = os.environ.get("ALPHA_SIGN_PORT")
    if not port:
        pytest.skip("set ALPHA_SIGN_PORT to the Sign's serial port")
    opened: list[Sign] = []

    def opener() -> Sign:
        serial = SerialTransport(
            port, baudrate=SETTINGS.baudrate, serial_format=SETTINGS.serial_format
        )
        recording = RecordingTransport(serial)
        captures.recordings.setdefault(request.node.nodeid, []).append(recording)
        sign = Sign(
            recording,
            model=SETTINGS.model,
            address=SETTINGS.address,
            strict=True,
            broadcast_reads=True,  # the hardware tests expect one Sign on the line
        )
        opened.append(sign)
        return sign

    yield opener
    for sign in opened:
        sign.close()


@pytest.fixture
def sign(open_sign: Callable[[], Sign], captures: Captures) -> Sign:
    opened = open_sign()
    if CAPTURE_PATH and captures.firmware is None:
        info = opened.info()
        captures.firmware = f"{info.firmware} rev {info.revision} ({info.firmware_date})"
        # Keep this read out of the test's own capture.
        recording = opened.transport
        assert isinstance(recording, RecordingTransport)
        setup = RecordingTransport(recording.inner, events=list(recording.events))
        recording.events.clear()
        captures.recordings.setdefault("setup: General Information", []).append(setup)
    return opened


@pytest.fixture
def ask(request: pytest.FixtureRequest) -> Callable[[str, str], str]:
    """Ask the person watching the Sign a question; return their one-letter answer."""
    if request.config.getoption("capture") != "no":
        pytest.skip("witnessed tests read answers: run them with -s")

    def asker(question: str, answers: str = "yn") -> str:
        while True:
            reply = input(f"\n{question} [{'/'.join(answers)}] ").strip().lower()
            if len(reply) == 1 and reply in answers:
                return reply

    return asker


# Automatic tests


def test_general_information_parses(sign: Sign) -> None:
    # Checklist: General Information length (28 or 29 characters, optional NUL).
    info = sign.info()

    assert info.memory_total >= info.memory_free


def test_the_signs_memory_matches_the_model(sign: Sign) -> None:
    # Checklist: total memory. The brochure says 28,000 bytes on the 4000 Series; a 4120C
    # reported 28,872 (docs/hardware-results.md), so the model's figure is the Sign's.
    if sign.model.memory_bytes is None:
        pytest.skip(f"{sign.model.name} has no memory size")

    assert sign.info().memory_total == sign.model.memory_bytes


def test_a_packet_arrives_without_serial_errors(sign: Sign) -> None:
    sign.serial_errors()  # reading resets the register
    sign.show("alpha-led-sign", mode=Mode.HOLD)

    assert sign.serial_errors().ok


def test_text_file_a_reads_back_as_written(sign: Sign) -> None:
    message = Message(Frame(Mode.ROTATE, Position.FILL, [Color.GREEN, "read back"]))

    sign.write_text("A", message)

    assert sign.read_text("A") == message


def test_clock_is_set(sign: Sign) -> None:
    now = datetime.now()

    sign.set_clock(now)

    assert sign.info().time.hour == now.hour


def test_priority_and_clear(sign: Sign) -> None:
    sign.priority(Frame(Mode.FLASH, Position.MIDDLE, "PRIORITY"))
    sign.clear_priority()

    assert sign.serial_errors().ok


def test_beep_then_more_data(sign: Sign) -> None:
    # The 3 s pause after a tone must be enough for the next Packet to arrive intact.
    sign.serial_errors()
    sign.beep(Tone.THREE_BEEPS)
    sign.show("after beep")

    assert sign.serial_errors().ok


def test_discovery_finds_this_sign(sign: Sign) -> None:
    # Checklist: the format of Network Query answers (`E-UAAZ`, assumed a Response Packet).
    found = discover(sign.transport, max_address=max(SETTINGS.address, 1))
    addresses = [answer.address for answer in found]

    if SETTINGS.address == 0:
        # 0 is the broadcast address: the Sign answers with its own address instead.
        assert addresses
    else:
        assert SETTINGS.address in addresses


@needs_readdress
def test_network_query_answers_at_a_second_sign_address(sign: Sign) -> None:
    # Captures a second answer for the discovery tests (p. 26, p. 32).
    original = SETTINGS.address
    second = 2 if original == 1 else 1
    sign.set_sign_address(second)
    try:
        found = discover(sign.transport, max_address=max(original, second))
    finally:
        sign.set_sign_address(original)

    assert second in [answer.address for answer in found]


@needs_erase
def test_string_file_updates_and_reads_back(sign: Sign) -> None:
    sign.configure_memory([TextFile("A", size=256), StringFile("T", size=16)])
    sign.write_text("A", Frame(Mode.HOLD, Position.FILL, ["Temp: ", StringRef("T")]))

    sign.write_string("T", "72F")

    assert sign.read_string("T") == ("72F",)
    assert sign.info().memory_total >= 256 + 16


def _used(sign: Sign, files: Sequence[MemoryFile]) -> int:
    """Configure ``files`` and return how much of the Sign's memory is in use."""
    sign.configure_memory(files)
    info = sign.info()
    return info.memory_total - info.memory_free


@needs_erase
def test_each_file_costs_its_size_plus_the_manuals_overhead(sign: Sign) -> None:
    # Checklist: per-File overhead. The model's value is 11 from p. 27, note 1;
    # the readerboard project (https://github.com/mjaksn/readerboard) reports 13.
    one = [TextFile("A", size=256)]
    three = [*one, TextFile("B", size=128), StringFile("T", size=16)]

    used_one = _used(sign, one)
    used_three = _used(sign, three)
    overhead = (used_three - used_one - (128 + 16)) / (len(three) - len(one))

    assert overhead == sign.model.file_overhead, f"measured {overhead} bytes per File"


@needs_erase
def test_a_dots_picture_file_costs_what_the_model_says(sign: Sign) -> None:
    # Checklist: p. 27, note 1 leaves DOTS PICTURE sizes out of the sum. A 4120C counts
    # them, and its model says how.
    base: list[MemoryFile] = [TextFile("A", size=256)]
    with_picture = [*base, DotsPictureFile("P", rows=16, columns=16)]

    extra = _used(sign, with_picture) - _used(sign, base)

    expected = sign.model.memory_needed(with_picture) - sign.model.memory_needed(base)
    assert extra == expected, f"a 16x16 DOTS PICTURE File used {extra} bytes"


@needs_erase
def test_the_largest_memory_configuration_the_sign_takes_is_the_models(sign: Sign) -> None:
    # Checklist: the Memory Configuration limit. The Sign gives unused memory to the first
    # TEXT File, so a refused configuration shows only as File B never being made.
    if sign.model.memory_bytes is None:
        pytest.skip(f"the {sign.model.name} profile has no memory size")
    other = TextFile("B", size=100)
    largest = sign.model.memory_bytes - sign.model.memory_needed([TextFile("A", size=0), other])

    sign.clear_memory()
    alone = _used(sign, [TextFile("A", size=256)])
    sign.clear_memory()
    at_limit = _used(sign, [TextFile("A", size=largest), other])
    sign.clear_memory()
    sign.strict = False  # the model refuses this one; send it anyway
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        past_limit = _used(sign, [TextFile("A", size=largest + 1), other])

    assert at_limit > alone, f"the Sign refused File A of {largest} bytes beside File B"
    assert past_limit < at_limit, f"the Sign took File A of {largest + 1} bytes beside File B"


# DOTS PICTURE Files

# Table 60, p. 76: a red arrow with one green pixel at its tip, 15 rows x 9 columns.
ARROW = DotsPicture.parse(
    "\n".join(
        [
            "000000000",
            "000000000",
            "000100000",
            "000110000",
            "000111000",
            "000111100",
            "111111110",
            "111111112",
            "111111110",
            "000111100",
            "000111000",
            "000110000",
            "000100000",
            "000000000",
            "000000000",
        ]
    )
)


def _picture_file(sign: Sign, label: str, picture: DotsPicture) -> DotsPictureFile:
    """A DOTS PICTURE File entry the size of ``picture``, in color if the model has it."""
    capabilities = sign.model.capabilities
    in_color = capabilities is None or Capability.COLOR in capabilities
    colors = PictureColors.TRICOLOR if in_color else PictureColors.MONOCHROME
    return DotsPictureFile(label, rows=picture.height, columns=picture.width, colors=colors)


@needs_erase
def test_a_dots_picture_reads_back_as_written(sign: Sign) -> None:
    # Checklist: the bytes of a J Response (Table 24). With ALPHA_SIGN_CAPTURE set, the
    # capture holds them.
    sign.configure_memory([TextFile("A", size=64), _picture_file(sign, "P", ARROW)])

    sign.write_dots_picture("P", ARROW)

    assert sign.read_dots_picture("P") == ARROW


@needs_erase
def test_a_dots_picture_of_another_size_than_its_file(
    sign: Sign, request: pytest.FixtureRequest
) -> None:
    # Checklist: p. 39 says the size must match the Memory Configuration. The library
    # does not check it; this records what the Sign does instead.
    small = DotsPicture.parse("11\n11")
    sign.configure_memory([TextFile("A", size=64), _picture_file(sign, "P", ARROW)])

    sign.write_dots_picture("P", small)
    back = sign.read_dots_picture("P")

    result = f"wrote 2x2 into a 9x15 File, read back {back.width}x{back.height}: {back.rows!r}"
    request.node.user_properties.append(("size mismatch", result))
    print(f"\n{result}")


@dataclass(frozen=True)
class UnpausedWriteDotsPicture(WriteDotsPicture):
    """A DOTS PICTURE write without the pause p. 40 asks for after the Width."""

    def encode_data(self) -> tuple[bytes | Pause, ...]:
        return tuple(piece for piece in super().encode_data() if not isinstance(piece, Pause))


@needs_erase
def test_a_dots_picture_written_without_the_pause(
    sign: Sign, request: pytest.FixtureRequest
) -> None:
    # Checklist: p. 40 asks for 100 ms after the Width. The library always pauses; this
    # records whether the Sign needs it.
    sign.configure_memory([TextFile("A", size=64), _picture_file(sign, "P", ARROW)])

    sign.send(UnpausedWriteDotsPicture("P", ARROW))
    intact = sign.read_dots_picture("P") == ARROW

    request.node.user_properties.append(("intact without the pause", intact))
    print(f"\nwithout the pause the picture arrived {'intact' if intact else 'damaged'}")


# Witnessed tests


@dataclass(frozen=True)
class RawWriteText(Command):
    """A TEXT File write with hand-built data, for forms the library will not build."""

    code: ClassVar[str] = "A"
    label: str
    data: bytes

    def encode_data(self) -> bytes:
        return self.label.encode("ascii") + self.data


@pytest.mark.witness
@needs_witness
def test_tone_repeats_do_not_count_the_first_play(
    sign: Sign, ask: Callable[[str, str], str]
) -> None:
    # Checklist: whether R (p. 22) counts the first play. The library waits for R + 1.
    sign.set_speaker(True)  # off by default (p. 21)
    repeats = 2
    sign.tone(frequency=0x80, duration=5, repeats=repeats)

    heard = ask("How many plays did you hear?", "123456")

    assert int(heard) == repeats + 1


@pytest.mark.parametrize(
    ("special_mode", "hex_specifier"),
    [(SpecialMode.NEWS_FLASH, b":"), (SpecialMode.TRUMPET, b";")],
)
@pytest.mark.witness
@needs_witness
def test_special_mode_letters_are_the_right_form(
    sign: Sign,
    ask: Callable[[str, str], str],
    request: pytest.FixtureRequest,
    special_mode: SpecialMode,
    hex_specifier: bytes,
) -> None:
    # Checklist: Table 66 gives "A"/"B" and also hex 3AH/3BH. The library sends letters,
    # so only the letter form can fail this test. The hex form's answer is recorded.
    # Appendix G limits these to the BetaBrite 1036: on a Sign whose profile leaves
    # them out, the test checks that neither form plays.
    name = special_mode.name.replace("_", " ")
    sign.strict = False  # the profile may say the Sign can't; send it anyway
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        sign.write_text("A", Frame(special_mode, Position.FILL, "LETTER"))
    letter = ask(f"Did the Sign show the {name} Special Mode before LETTER?", "yn")
    mode_field = b"\x1b" + Position.FILL.value.encode("ascii") + b"n" + hex_specifier
    sign.send(RawWriteText("A", mode_field + b"HEX"))
    hexed = ask(f"Did the Sign show the {name} Special Mode before HEX?", "yn")

    results = {"letter form": letter, "hex form": hexed}
    request.node.user_properties.extend(results.items())
    print(f"\n{name}: letter form {letter}, hex form {hexed}")
    capabilities = sign.model.capabilities
    if capabilities is None or Capability.BETABRITE_1036_ANIMATIONS in capabilities:
        assert letter == "y", f"{name}: letter form no, hex form {hexed}"
    else:
        assert (letter, hexed) == ("n", "n"), (
            f"{name}: letter form {letter}, hex form {hexed}, "
            f"but the {sign.model.name} profile says it cannot"
        )


@pytest.mark.parametrize(
    ("capability", "content", "question"),
    [
        (
            Capability.NEW_PAGE,
            ["PAGE ONE", Control.NEW_PAGE, "PAGE TWO"],
            "Did PAGE TWO replace PAGE ONE as a new page?",
        ),
        (
            Capability.DOUBLE_HIGH,
            [DoubleHigh(on=True), "TALL", DoubleHigh(on=False)],
            "Was TALL shown in double-height characters?",
        ),
    ],
)
@pytest.mark.witness
@needs_witness
def test_the_model_knows_whether_the_sign_does_it(
    sign: Sign,
    ask: Callable[[str, str], str],
    capability: Capability,
    content: list[Segment],
    question: str,
) -> None:
    # Checklist: Tables 69 and 70 have no NEW_PAGE or double height for the 4000 Series.
    sign.strict = False  # the profile may say the Sign can't; send it anyway
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        sign.write_text("A", Frame(Mode.HOLD, Position.FILL, content))
    did_it = ask(question, "yn") == "y"

    in_profile = sign.model.capabilities is None or capability in sign.model.capabilities
    assert did_it == in_profile, (
        f"the Sign {'did' if did_it else 'did not'} do {capability.value}, "
        f"but the {sign.model.name} profile says it {'can' if in_profile else 'cannot'}"
    )


@pytest.mark.witness
@needs_witness
def test_the_two_digit_year_is_read_as_20xx(sign: Sign, ask: Callable[[str, str], str]) -> None:
    # Checklist: p. 28, note 15 gives the 1997-2096 window for Alpha 2.0 and later only.
    sign.set_clock(datetime(2026, 11, 7, 12, 0))
    try:
        sign.show([CurrentDate(DateFormat.MMM_DD_YYYY)])
        answer = ask("Does the Sign show the year 2026 (NOV.07, 2026)?", "yn")
    finally:
        sign.set_clock(datetime.now())

    assert answer == "y"


@pytest.mark.witness
@needs_witness
@needs_erase
def test_a_dots_picture_is_drawn_between_the_text_around_it(
    sign: Sign, ask: Callable[[str, str], str]
) -> None:
    # Checklist: the manual doesn't say where a called picture goes. A 4120C drew it at
    # the text cursor, cut to the arrow's top 8 rows: the head's upper half and the
    # shaft's top two rows, with the green tip at the bottom right.
    sign.configure_memory([TextFile("A", size=64), _picture_file(sign, "P", ARROW)])
    sign.write_dots_picture("P", ARROW)

    sign.write_text("A", Frame(Mode.HOLD, Position.FILL, ["AB", DotsPictureRef("P"), "CD"]))

    print("\nExpected between AB and CD: the top half of a right arrow, a green dot at its")
    print("bottom right. The arrow's first two rows are blank, so its top lit dot is two")
    print("rows below the letters' top; its bottom row is one row below the letters'.")
    assert ask("Is that what the Sign shows?", "yn") == "y"


# A column of 15 lit dots, easy to count. No Sign line is taller than 16 rows.
BAR = DotsPicture.parse("\n".join(["1"] * 15))


@pytest.mark.witness
@needs_witness
@needs_erase
@pytest.mark.parametrize(("font", "text_height"), [(Font.FIVE_HIGH, 5), (Font.SEVEN_HIGH, 7)])
def test_a_dots_picture_is_cut_to_8_rows(
    sign: Sign,
    ask: Callable[[str, str], str],
    request: pytest.FixtureRequest,
    font: Font,
    text_height: int,
) -> None:
    # Checklist: the manual doesn't say where a called picture goes, and p. 96 says Fill
    # shows at most 7 of its rows. On a 4120C the line holding a picture is 8 rows,
    # centered on the display: the picture fills it from the top, cut to 8 rows, and
    # five high and seven high text ends one row above its bottom. (Full height is
    # seven high in Fill, p. 96; TEN_HIGH is not on the 4000 Series, Table 69.)
    sign.configure_memory([TextFile("A", size=64), _picture_file(sign, "P", BAR)])
    sign.write_dots_picture("P", BAR)
    sign.write_text("A", Frame(Mode.HOLD, Position.FILL, [font, "AB", DotsPictureRef("P"), "CD"]))

    tall, bar_top, text_top = _count_the_bar(ask, request, font.name)

    rows = sign.model.rows or 16
    assert (tall, bar_top) == (8, (rows - 8) // 2)
    assert text_top == bar_top + 7 - text_height


@pytest.mark.witness
@needs_witness
@needs_erase
def test_a_dots_picture_in_middle_is_not_cut_to_8_rows(
    sign: Sign, ask: Callable[[str, str], str], request: pytest.FixtureRequest
) -> None:
    # Checklist: p. 95 says Middle is one line 16 dots high and cuts only a picture
    # taller than that; p. 96 says 15. A 4120C showed all 15 rows of the bar beside
    # full height text, from the display's top row, level with the letters' top.
    sign.configure_memory([TextFile("A", size=64), _picture_file(sign, "P", BAR)])
    sign.write_dots_picture("P", BAR)
    sign.write_text(
        "A", Frame(Mode.HOLD, Position.MIDDLE, [Font.FULL_HEIGHT, "AB", DotsPictureRef("P"), "CD"])
    )

    tall, bar_top, text_top = _count_the_bar(ask, request, "FULL_HEIGHT in MIDDLE")

    assert (tall, bar_top, text_top) == (len(BAR.rows), 0, 0)


def _count_the_bar(
    ask: Callable[[str, str], str], request: pytest.FixtureRequest, case: str
) -> tuple[int, int, int]:
    """Ask for the bar's height and the unlit rows above it and above the A; record them."""
    print(f"\n{case}. Count in hex (a = 10, b = 11, ...).")
    tall = int(ask("How many dots tall is the bar between AB and CD?", "0123456789abcdef"), 16)
    bar_top = int(ask("How many unlit rows are above the bar?", "0123456789abcdef"), 16)
    text_top = int(ask("How many unlit rows are above the letter A?", "0123456789abcdef"), 16)
    result = f"bar {tall} tall, {bar_top} rows above the bar, {text_top} above the A"
    request.node.user_properties.append(("bar", result))
    print(f"{case}: {result}")
    return tall, bar_top, text_top


@pytest.mark.witness
@needs_witness
@pytest.mark.parametrize(
    ("position", "question"),
    [
        (Position.FILL, "Are ABCD seven dots tall, like ordinary text?"),
        (Position.MIDDLE, "Are ABCD as tall as the display?"),
    ],
)
def test_full_height_text_is_full_height_only_in_middle(
    sign: Sign, ask: Callable[[str, str], str], position: Position, question: str
) -> None:
    # Checklist: p. 96 says a two-line Sign "will 'size down'" a font larger than
    # 7-high in the Top, Bottom, or Fill position; p. 95 says Middle is one line 16
    # dots high. The library warns about the first.
    sign.strict = False
    frame = Frame(Mode.HOLD, position, [Font.FULL_HEIGHT, "ABCD"])
    if position is Position.MIDDLE:
        sign.write_text("A", frame)
    else:
        with pytest.warns(UnsupportedCapabilityWarning, match="7-high"):
            sign.write_text("A", frame)

    assert ask(question, "yn") == "y"


@pytest.mark.witness
@needs_witness
@needs_erase
def test_which_pixel_colors_the_sign_shows(
    sign: Sign, ask: Callable[[str, str], str], request: pytest.FixtureRequest
) -> None:
    # Checklist: p. 40 lists colors 1-8, and "some signs do not support the full range".
    # The library does not check 4-8 on a tricolor Sign; this records what it shows.
    bands = DotsPicture.parse("\n".join(["".join(code * 4 for code in "12345678")] * 8))
    sign.configure_memory([TextFile("A", size=64), _picture_file(sign, "P", bands)])
    sign.write_dots_picture("P", bands)
    sign.write_text("A", Frame(Mode.HOLD, Position.FILL, [DotsPictureRef("P")]))

    print(
        "\nEight bands, left to right: red, green, amber, dim red, dim green, brown, "
        "orange, yellow."
    )
    lit = ask("How many bands are lit?", "012345678")
    distinct = ask("How many different colors do the lit bands show?", "012345678")

    request.node.user_properties.extend([("bands lit", lit), ("distinct colors", distinct)])
