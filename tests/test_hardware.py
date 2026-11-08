"""Smoke tests against a real Sign. Opt-in: they never run against a real Sign in CI.

    ALPHA_SIGN_PORT=/dev/tty.usbserial-1410 uv run pytest -m hardware

The same tests run against the emulator (Node and ``npm ci`` in emulator/), which
needs no settings. Erase and re-address tests run there without their opt-in flags:

    uv run pytest -m emulator

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
  showed or played. They read your answers, so run them with ``-s``:

      ALPHA_SIGN_PORT=... ALPHA_SIGN_WITNESS=1 uv run pytest -m witness -s

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
    DotsPictureFile,
    DoubleHigh,
    Frame,
    Message,
    Mode,
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
from alpha_led_sign.protocol.commands import (
    Command,
    Tone,
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
needs_network_query = pytest.mark.skipif(
    EMULATED, reason="the emulator does not answer Network Query yet (deferred past its MVP)"
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
        sign = Sign(recording, model=SETTINGS.model, address=SETTINGS.address, strict=True)
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
    # Checklist: total memory. Table 5 and the brochure: 28,000 bytes on the 4000 Series.
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


@needs_network_query
def test_discovery_finds_this_sign(sign: Sign) -> None:
    # Checklist: the format of Network Query answers (`E-UAAZ`, assumed a Response Packet).
    found = discover(sign.transport, max_address=max(SETTINGS.address, 1))

    assert SETTINGS.address in [answer.address for answer in found]


@needs_network_query
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
def test_a_dots_picture_file_costs_only_the_overhead(sign: Sign) -> None:
    # Checklist: p. 27, note 1 leaves DOTS PICTURE sizes out of the sum. The library
    # assumes the per-File overhead still counts.
    base = [TextFile("A", size=256)]

    used_base = _used(sign, base)
    used_with_picture = _used(sign, [*base, DotsPictureFile("P", rows=16, columns=16)])

    extra = used_with_picture - used_base
    assert extra == sign.model.file_overhead, f"a 16x16 DOTS PICTURE File used {extra} bytes"


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
    name = special_mode.name.replace("_", " ")
    sign.write_text("A", Frame(special_mode, Position.FILL, "LETTER"))
    letter = ask(f"Did the Sign show the {name} Special Mode before LETTER?", "yn")
    mode_field = b"\x1b" + Position.FILL.value.encode("ascii") + b"n" + hex_specifier
    sign.send(RawWriteText("A", mode_field + b"HEX"))
    hexed = ask(f"Did the Sign show the {name} Special Mode before HEX?", "yn")

    results = {"letter form": letter, "hex form": hexed}
    request.node.user_properties.extend(results.items())
    print(f"\n{name}: letter form {letter}, hex form {hexed}")
    assert letter == "y", f"{name}: letter form no, hex form {hexed}"


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
