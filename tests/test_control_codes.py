"""The Control Code table: one entry per Control Code type, read by every module that
needs a fact about one."""

import inspect

import pytest

from alpha_led_sign.protocol import codes
from alpha_led_sign.protocol.codes import ControlCode, RawControl
from alpha_led_sign.protocol.control_codes import KINDS, decode_control, examples


def control_code_types() -> set[type]:
    """Every class in ``codes`` whose instances or members encode to Control Code bytes."""
    return {
        cls
        for _, cls in inspect.getmembers(codes, inspect.isclass)
        if cls.__module__ == codes.__name__ and cls is not ControlCode and "encode" in vars(cls)
    }


def test_every_control_code_type_has_one_entry() -> None:
    # A new Control Code type fails here, before it can be sent unchecked.
    assert {kind.type for kind in KINDS} == control_code_types()
    assert len(KINDS) == len({kind.type for kind in KINDS})


@pytest.mark.parametrize(
    "code",
    [code for kind in KINDS for code in examples(kind)],
    ids=repr,
)
def test_every_known_control_code_decodes_to_itself(code: ControlCode) -> None:
    data = code.encode() + b"x"

    assert decode_control(data, 0) == (code, len(data) - 1)


def test_raw_control_codes_have_no_examples() -> None:
    # Their bytes are whatever the Sign sent; they decode only when nothing else does.
    (raw,) = (kind for kind in KINDS if kind.type is RawControl)
    assert examples(raw) == ()
