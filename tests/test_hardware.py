"""Smoke tests against a real Sign. Opt-in: they never run in CI.

    ALPHA_SIGN_PORT=/dev/tty.usbserial-1410 uv run pytest -m hardware

Optional settings:

- ALPHA_SIGN_MODEL: a registered Sign Model name (default 4120C).
- ALPHA_SIGN_ADDRESS: the Sign Address (default 0).
- ALPHA_SIGN_BAUD: baud rate (default 9600).
- ALPHA_SIGN_FORMAT: 8N1 (default) or 7E2.
- ALPHA_SIGN_ALLOW_ERASE=1: also run tests that write the Memory Configuration,
  which ERASES EVERY FILE on the Sign.

Each test maps to an item on the hardware checklist in docs/plan.md (Phase 8).
"""

import os
from collections.abc import Iterator
from datetime import datetime

import pytest

from alpha_led_sign import (
    Color,
    Frame,
    Message,
    Mode,
    Position,
    SerialFormat,
    Sign,
    StringFile,
    StringRef,
    TextFile,
    discover,
    models,
)
from alpha_led_sign.protocol.commands import Tone

pytestmark = pytest.mark.hardware

PORT = os.environ.get("ALPHA_SIGN_PORT")
ALLOW_ERASE = os.environ.get("ALPHA_SIGN_ALLOW_ERASE") == "1"
needs_erase = pytest.mark.skipif(not ALLOW_ERASE, reason="set ALPHA_SIGN_ALLOW_ERASE=1")


@pytest.fixture
def sign() -> Iterator[Sign]:
    if not PORT:
        pytest.skip("set ALPHA_SIGN_PORT to the Sign's serial port")
    serial_format = {"8N1": SerialFormat.EIGHT_N_ONE, "7E2": SerialFormat.SEVEN_E_TWO}[
        os.environ.get("ALPHA_SIGN_FORMAT", "8N1")
    ]
    with Sign.serial(
        PORT,
        model=models.get(os.environ.get("ALPHA_SIGN_MODEL", "4120C")),
        address=int(os.environ.get("ALPHA_SIGN_ADDRESS", "0")),
        baudrate=int(os.environ.get("ALPHA_SIGN_BAUD", "9600")),
        serial_format=serial_format,
        strict=True,
    ) as opened:
        yield opened


def test_general_information_parses(sign: Sign) -> None:
    # Checklist: General Information length (28 or 29 characters, optional NUL).
    info = sign.info()

    assert info.memory_total >= info.memory_free


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


def test_discovery_finds_this_sign() -> None:
    # Checklist: the format of Network Query answers.
    if not PORT:
        pytest.skip("set ALPHA_SIGN_PORT to the Sign's serial port")
    address = int(os.environ.get("ALPHA_SIGN_ADDRESS", "0"))
    with Sign.serial(PORT) as opened:
        found = discover(opened.transport, max_address=max(address, 1))

    assert address in [sign.address for sign in found]


@needs_erase
def test_string_file_updates_and_reads_back(sign: Sign) -> None:
    sign.configure_memory([TextFile("A", size=256), StringFile("T", size=16)])
    sign.write_text("A", Frame(Mode.HOLD, Position.FILL, ["Temp: ", StringRef("T")]))

    sign.write_string("T", "72F")

    assert sign.read_string("T") == ("72F",)
    assert sign.info().memory_total >= 256 + 16
