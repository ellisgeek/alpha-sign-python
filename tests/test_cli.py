"""The ``alpha-led-sign`` command over an in-memory Line: what it prints, and what it
refuses to send."""

import pytest
from typer.testing import CliRunner

from alpha_led_sign.cli import app
from tests.fakes import FakeLine
from tests.vectors import TABLE_46, TABLE_59

runner = CliRunner()


@pytest.fixture
def line(monkeypatch: pytest.MonkeyPatch) -> FakeLine:
    """The Line the command opens, whatever port it is given."""
    fake = FakeLine()
    monkeypatch.setattr("alpha_led_sign.sign.SerialTransport", lambda *_, **__: fake)
    for name in ("PORT", "MODEL", "ADDRESS", "BAUD", "FORMAT"):
        monkeypatch.delenv(f"ALPHA_SIGN_{name}", raising=False)
    return fake


def test_read_prints_the_text_file_from_table_46(line: FakeLine) -> None:
    line.answer(b"BC", TABLE_46)

    result = runner.invoke(app, ["--port", "loop://", "--model", "Generic", "read", "C"])

    assert result.exit_code == 0
    assert result.stdout == "{frame}FILE C\n"  # no Mode Field in Table 46
    assert line.closed


def test_read_string_prints_the_string_file_from_table_59(line: FakeLine) -> None:
    line.answer(b"H2", TABLE_59)

    result = runner.invoke(
        app, ["--port", "loop://", "--model", "Generic", "read", "2", "--string"]
    )

    assert result.stdout == "8,234,000\n"


def test_the_port_can_come_from_alpha_led_sign_port(line: FakeLine) -> None:
    line.answer(b"BC", TABLE_46)

    result = runner.invoke(
        app, ["--model", "Generic", "read", "C"], env={"ALPHA_SIGN_PORT": "loop://"}
    )

    assert result.stdout == "{frame}FILE C\n"


def test_a_read_with_no_answer_is_an_error_without_a_traceback(line: FakeLine) -> None:
    result = runner.invoke(app, ["--port", "loop://", "read", "A"])

    assert result.exit_code == 1
    assert "error:" in result.stderr
    assert "Traceback" not in result.output


def test_without_a_port_it_is_a_usage_error_and_sends_nothing(line: FakeLine) -> None:
    result = runner.invoke(app, ["show", "Hello"])

    assert result.exit_code == 2
    assert "ALPHA_SIGN_PORT" in result.stderr
    assert line.written == b""


def test_configure_sends_nothing_unless_the_erase_is_confirmed(line: FakeLine) -> None:
    result = runner.invoke(app, ["--port", "loop://", "configure", "A:text:512"], input="n\n")

    assert result.exit_code == 1
    assert "not changed" in result.stderr
    assert line.written == b""


def test_a_bad_memory_file_is_a_usage_error_and_sends_nothing(line: FakeLine) -> None:
    result = runner.invoke(app, ["--port", "loop://", "configure", "A:text:big", "--yes"])

    assert result.exit_code == 2
    assert line.written == b""
