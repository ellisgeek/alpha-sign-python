"""The Control Code table: what the library knows about each Control Code type.

Each type has one entry. Decoding, the Capability each code needs, and which codes a
STRING File may hold are all read from it, so a new type is one entry, and a test
fails while any Control Code type has none.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from alpha_led_sign.protocol.capabilities import Capability
from alpha_led_sign.protocol.codes import (
    Attribute,
    CharacterAttribute,
    CharacterFlash,
    Color,
    Control,
    ControlCode,
    CurrentDate,
    CurrentTime,
    DateFormat,
    DotsPictureRef,
    DoubleHigh,
    Font,
    RawControl,
    Spacing,
    Speed,
    StringRef,
    TrueDescenders,
    Wide,
)


@dataclass(frozen=True)
class ControlCodeKind[C: ControlCode]:
    """Everything the library knows about one Control Code type."""

    type: type[C]
    values: tuple[C, ...]
    """Every value of the type, for decoding. Empty for a File Label reference, whose
    values are its lead byte plus any label, and for RawControl."""
    capability: Callable[[C], Capability | None]
    """The Capability a value needs (Tables 68-70, Appendix G), or None."""
    in_string_file: Callable[[C], bool] = field(default=lambda _: False)
    """Whether a STRING File may hold the value (Table 19, p. 37)."""
    label_lead: int | None = None
    """For a File Label reference: the byte before the label (Appendix G, p. 81)."""


def _switches[S](make: Callable[[bool], S]) -> tuple[S, ...]:
    return (make(True), make(False))


def _always[C](capability: Capability) -> Callable[[C], Capability | None]:
    return lambda _: capability


# Appendix G, p. 82, note 1: "only applies to Betabrite model 1036 signs."
_FONTS = {
    Font.FIVE_HIGH: Capability.FONT_FIVE_HIGH,
    Font.SEVEN_HIGH: Capability.FONT_SEVEN_HIGH,
    Font.SEVEN_HIGH_FANCY: Capability.FONT_SEVEN_HIGH_FANCY,
    Font.TEN_HIGH: Capability.FONT_TEN_HIGH,
    Font.FULL_HEIGHT_FANCY: Capability.FONT_FULL_HEIGHT_FANCY,
    Font.FULL_HEIGHT: Capability.FONT_FULL_HEIGHT,
    Font.FIVE_STROKE: Capability.BETABRITE_1036_FONTS,
    Font.SEVEN_STROKE: Capability.BETABRITE_1036_FONTS,
    Font.SEVEN_SHADOW: Capability.BETABRITE_1036_FONTS,
    Font.SEVEN_SHADOW_FANCY: Capability.BETABRITE_1036_FONTS,
    Font.FIVE_WIDE: Capability.BETABRITE_1036_FONTS,
    Font.SEVEN_WIDE: Capability.BETABRITE_1036_FONTS,
    Font.SEVEN_FANCY_WIDE: Capability.BETABRITE_1036_FONTS,
    Font.WIDE_STROKE_FIVE: Capability.BETABRITE_1036_FONTS,
}

_ATTRIBUTES = {
    Attribute.WIDE: Capability.WIDE,
    Attribute.DOUBLE_WIDE: Capability.DOUBLE_WIDE,
    Attribute.DOUBLE_HIGH: Capability.DOUBLE_HIGH,
    Attribute.TRUE_DESCENDERS: Capability.TRUE_DESCENDERS,
    Attribute.FIXED_WIDTH: Capability.FIXED_WIDTH,
    Attribute.AUXILIARY_PORT: Capability.AUXILIARY_PORT,  # Appendix G, p. 82
    Attribute.SHADOW: Capability.SHADOW,  # Appendix G, p. 82
}

_CONTROLS = {Control.NEW_LINE: Capability.NEW_LINE, Control.NEW_PAGE: Capability.NEW_PAGE}

KINDS: tuple[ControlCodeKind[Any], ...] = (
    ControlCodeKind(
        Color,
        tuple(Color),
        _always(Capability.COLOR),
        in_string_file=lambda color: color not in (Color.RAINBOW_1, Color.RAINBOW_2),
    ),
    ControlCodeKind(Font, tuple(Font), _FONTS.__getitem__, in_string_file=lambda _: True),
    ControlCodeKind(Speed, tuple(Speed), _always(Capability.SPEED), in_string_file=lambda _: True),
    ControlCodeKind(
        Control,
        tuple(Control),
        _CONTROLS.__getitem__,
        in_string_file=lambda control: control is Control.NEW_LINE,
    ),
    ControlCodeKind(
        Spacing,
        tuple(Spacing),
        lambda spacing: Capability.FIXED_WIDTH if spacing is Spacing.FIXED_WIDTH else None,
        in_string_file=lambda _: True,
    ),
    ControlCodeKind(Wide, _switches(Wide), _always(Capability.WIDE), in_string_file=lambda _: True),
    ControlCodeKind(DoubleHigh, _switches(DoubleHigh), _always(Capability.DOUBLE_HIGH)),
    ControlCodeKind(TrueDescenders, _switches(TrueDescenders), _always(Capability.TRUE_DESCENDERS)),
    ControlCodeKind(CharacterFlash, _switches(CharacterFlash), _always(Capability.CHARACTER_FLASH)),
    ControlCodeKind(
        CharacterAttribute,
        tuple(CharacterAttribute(a, on) for a in Attribute for on in (True, False)),
        lambda code: _ATTRIBUTES.get(code.attribute),
    ),
    ControlCodeKind(
        CurrentTime, (CurrentTime(),), _always(Capability.TIME), in_string_file=lambda _: True
    ),
    ControlCodeKind(
        CurrentDate, tuple(CurrentDate(f) for f in DateFormat), _always(Capability.DATE)
    ),
    ControlCodeKind(StringRef, (), _always(Capability.STRING), label_lead=0x10),
    # p. 81; Table 70's Graphic column.
    ControlCodeKind(DotsPictureRef, (), _always(Capability.GRAPHIC), label_lead=0x14),
    ControlCodeKind(RawControl, (), lambda _: None),
)
"""One entry per Control Code type."""

_BY_TYPE: dict[type, ControlCodeKind[Any]] = {kind.type: kind for kind in KINDS}


def kind_of(code: object) -> ControlCodeKind[Any] | None:
    """The table entry for ``code``'s type, or None if it is not a Control Code."""
    return _BY_TYPE.get(type(code))


def examples(kind: ControlCodeKind[Any]) -> tuple[ControlCode, ...]:
    """Every value of ``kind``, or one with File Label ``A`` for a label reference."""
    if kind.label_lead is not None:
        return (kind.type("A"),)
    return kind.values


def allowed_in_string_file(segment: object) -> bool:
    """Table 19, p. 37: whether a STRING File may hold ``segment``. Text always may."""
    if isinstance(segment, str):
        return True
    kind = kind_of(segment)
    return kind is not None and kind.in_string_file(segment)


# Decoding

_BY_BYTES: dict[bytes, ControlCode] = {
    value.encode(): value for kind in KINDS for value in kind.values
}
_LABEL_REFS: dict[int, Callable[[str], ControlCode]] = {
    kind.label_lead: kind.type for kind in KINDS if kind.label_lead is not None
}
_LONGEST = max(len(data) for data in _BY_BYTES)

# How many bytes a code with a known lead byte takes, so one with a parameter the
# library doesn't know is kept whole as a RawControl.
_LENGTHS: dict[int, int] = {
    **{data[0]: len(data) for data in _BY_BYTES},
    **dict.fromkeys(_LABEL_REFS, 2),
    0x08: 2,  # extended character, temperature, or counter (Appendix G)
    0x1F: 15,  # call picture or animation File (Appendix G)
}


def decode_control(data: bytes, start: int) -> tuple[ControlCode, int]:
    """Decode the Control Code at ``data[start]``; return it and the index after it."""
    for length in range(_LONGEST, 0, -1):
        code = _BY_BYTES.get(data[start : start + length])
        if code is not None:
            return code, start + length
    first = data[start]
    if first in _LABEL_REFS and start + 1 < len(data):
        try:
            return _LABEL_REFS[first](chr(data[start + 1])), start + 2
        except ValueError:
            pass  # not a File Label
    if first == 0x1C and data[start + 1 : start + 2] in (b"Y", b"Z"):
        end = start + 8  # 1CH + "Y" or "Z" + RRGGBB (Alpha 3.0)
    else:
        end = start + _LENGTHS.get(first, 1)
    return RawControl(data[start:end]), min(end, len(data))
