"""Start the emulator's headless host and drive its control channel.

The host is the Node program in ``emulator/`` (``npm run headless``). It listens for the
library on a TCP port, which ``SerialTransport`` reaches as ``socket://127.0.0.1:<port>``,
and serves a JSON control channel over HTTP (see ``emulator/src/host/headless.ts``).
"""

import json
import re
import shutil
import subprocess
import urllib.request
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Self

EMULATOR_DIR = Path(__file__).resolve().parent.parent / "emulator"
_PORTS = re.compile(r"tcp=(\d+) http=(\d+)")


@dataclass(frozen=True)
class SignSpec:
    """One Emulated Sign on the Line, as the host's ``SignSpec`` describes it.

    ``readings`` overrides some of the emulator's Readings by their names in
    ``emulator/src/core/readings.ts``; the rest keep their defaults.
    """

    sign_address: int
    model: str = "4120C"
    readings: Mapping[str, str | int | bool] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "signAddress": self.sign_address,
            "readings": dict(self.readings),
        }


# Set by tests/conftest.py from ``-m`` before the test modules are collected.
selected: bool = False


def selects_emulator(markexpr: str) -> bool:
    """Whether a ``-m`` expression asks for the emulator run (``-m emulator``)."""
    return re.search(r"(?<!not )\bemulator\b", markexpr) is not None


def unavailable() -> str | None:
    """Why the emulator can't start here, or None if it can."""
    if shutil.which("node") is None:
        return "the emulator needs Node; install the version in emulator/.nvmrc"
    if not (EMULATOR_DIR / "node_modules" / "tsx").is_dir():
        return "the emulator's npm packages are missing; run npm ci in emulator/"
    return None


class Emulator:
    """A running headless host. Close it when done (or use it as a context manager)."""

    def __init__(self, process: subprocess.Popen[str], tcp_port: int, http_port: int) -> None:
        self.process = process
        self.tcp_port = tcp_port
        self.http_port = http_port

    @classmethod
    def start(cls) -> Self:
        """Start the host on free ports and wait until it prints them."""
        process = subprocess.Popen(
            ["node", "--import", "tsx", "src/host/main.ts", "headless"],
            cwd=EMULATOR_DIR,
            stdout=subprocess.PIPE,
            text=True,
        )
        assert process.stdout is not None
        line = process.stdout.readline()
        found = _PORTS.search(line)
        if found is None:
            process.kill()
            process.wait()
            raise RuntimeError(f"the emulator host did not print its ports: {line!r}")
        return cls(process, int(found[1]), int(found[2]))

    @property
    def port(self) -> str:
        """The URL to give ``SerialTransport`` (and ``ALPHA_SIGN_PORT``)."""
        return f"socket://127.0.0.1:{self.tcp_port}"

    def reset(self, signs: Sequence[SignSpec] | None = None, clock: datetime | None = None) -> Any:
        """Power up a new Line with these Signs, their clocks starting at ``clock``.

        ``clock`` is the Signs' local time, so it must be naive. Either left out keeps
        the host's choice (the current Signs; the host's local time).
        """
        body: dict[str, Any] = {}
        if signs is not None:
            body["signs"] = [sign.to_json() for sign in signs]
        if clock is not None:
            if clock.tzinfo is not None:
                raise ValueError("clock is the Signs' local time; pass a naive datetime")
            body["clock"] = clock.isoformat(timespec="milliseconds")
        return self._call("POST", "/reset", body)

    def snapshots(self) -> list[dict[str, Any]]:
        """Each Emulated Sign's state, in Line order."""
        return self._call("GET", "/snapshots")

    def _call(self, method: str, path: str, body: object = None) -> Any:
        data = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.http_port}{path}",
            data=data,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=10) as reply:
            return json.load(reply)

    def close(self) -> None:
        self.process.terminate()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
