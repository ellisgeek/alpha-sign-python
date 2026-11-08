"""The emulator run: ``uv run pytest -m emulator`` runs the hardware tests against the
emulator's headless host instead of a real Sign."""

import os
from collections.abc import Iterator

import pytest

from tests import emulator
from tests.emulator import Emulator, SignSpec

# The emulator run's Line: one 4120C at Sign Address 1, so the tests can address it
# by number. tests/test_hardware.py reads its settings from here.
EMULATED_SIGN = SignSpec(model="4120C", sign_address=1)


def pytest_configure(config: pytest.Config) -> None:
    emulator.selected = emulator.selects_emulator(config.option.markexpr)
    if emulator.selected and os.environ.get("ALPHA_SIGN_CAPTURE"):
        raise pytest.UsageError(
            "ALPHA_SIGN_CAPTURE is refused under the emulator: emulator captures must never "
            "become test vectors"
        )


@pytest.fixture(scope="session")
def emulated_sign() -> Iterator[Emulator]:
    """Start the headless host with one 4120C and point ALPHA_SIGN_PORT at it."""
    reason = emulator.unavailable()
    if reason:
        pytest.skip(reason)
    with Emulator.start() as host, pytest.MonkeyPatch.context() as env:
        host.reset(signs=[EMULATED_SIGN])
        env.setenv("ALPHA_SIGN_PORT", host.port)
        yield host
