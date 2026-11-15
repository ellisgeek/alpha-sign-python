"""Markup: content written as one string, such as ``"{color red}Temp: {string T}"``.

Text is literal except for tokens in braces; ``{{`` and ``}}`` are literal braces. A
token is a kind and its values, separated by spaces. An enum value is spelled as the
member name in lowercase, without the kind as a prefix: ``Speed.SPEED_3`` is
``{speed 3}``. Kinds and values ignore case; File Labels don't. Literal text must be
printable ASCII.

| Token | Segment |
|---|---|
| ``{frame MODE [POSITION]}`` | Starts a Frame (see ``parse_markup``) |
| ``{color NAME}`` | ``Color`` |
| ``{font NAME}`` | ``Font`` |
| ``{speed 1}``...``{speed 5}``, ``{speed no_hold}`` | ``Speed`` |
| ``{spacing proportional}``, ``{spacing fixed_width}`` | ``Spacing`` |
| ``{wide}``, ``{double_high}`` | ``Wide``, ``DoubleHigh`` |
| ``{descenders}``, ``{flash}`` | ``TrueDescenders``, ``CharacterFlash`` |
| ``{attribute NAME [on/off]}`` | ``CharacterAttribute`` |
| ``{time}``, ``{date [FORMAT]}`` | ``CurrentTime``, ``CurrentDate`` |
| ``{new_line}``, ``{new_page}`` | ``Control`` |
| ``{string LABEL}``, ``{picture LABEL}`` | ``StringRef``, ``DotsPictureRef`` |
| ``{raw HEX}`` | ``RawControl`` |

``{wide}``, ``{double_high}``, ``{descenders}``, ``{flash}``, and ``{attribute ...}``
take ``on`` (the default) or ``off``. ``{raw HEX}`` holds Control Code bytes the
library does not model.

The syntax is recorded in docs/adr/0004-markup-syntax.md.
"""

from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import cast

from alpha_led_sign.protocol.codes import (
    Attribute,
    CharacterAttribute,
    CharacterFlash,
    Color,
    Control,
    CurrentDate,
    CurrentTime,
    DateFormat,
    DotsPictureRef,
    DoubleHigh,
    Font,
    Mode,
    Position,
    RawControl,
    Spacing,
    SpecialGraphic,
    SpecialMode,
    Speed,
    StringRef,
    TrueDescenders,
    Wide,
)
from alpha_led_sign.protocol.message import Frame, Message, Segment


class MarkupError(ValueError):
    """Markup that can't be read.

    The message names the problem and the character it is at.

    Args:
        message: What is wrong.
        position: The offset of the problem in the markup.

    Attributes:
        position: The offset of the problem in the markup, counted from 0.
    """

    def __init__(self, message: str, position: int) -> None:
        super().__init__(f"{message} (at character {position})")
        self.position = position


def escape_markup(text: str) -> str:
    """Make text literal in markup by doubling its braces.

    Pass any value from outside the program through this before you put it in
    markup, so that it can't add tokens.

    Args:
        text: The text to keep literal.

    Returns:
        The text with each ``{`` and ``}`` doubled.

    Examples:
        >>> from alpha_led_sign import escape_markup
        >>> escape_markup("{color red}")
        '{{color red}}'
    """
    return text.replace("{", "{{").replace("}", "}}")


def parse_segments(text: str) -> tuple[Segment, ...]:
    """Read markup into Segments, as a Frame or a STRING File holds them.

    Args:
        text: Markup without ``{frame ...}`` tokens.

    Returns:
        The literal text and Control Codes, in order.

    Raises:
        MarkupError: The markup can't be read, or it has a ``{frame}`` token:
            Segments belong to one Frame.

    Examples:
        >>> from alpha_led_sign import parse_segments
        >>> parse_segments("{color red}Hot")
        (<Color.RED: '1'>, 'Hot')
    """
    segments: list[Segment] = []
    for item in _scan(text):
        if isinstance(item, _Token):
            if item.kind == "frame":
                raise MarkupError("{frame} starts a Frame, which only a Message has", item.position)
            segments.append(_segment(item))
        else:
            segments.append(item)
    return tuple(segments)


type FrameMode = Mode | SpecialMode | SpecialGraphic | None


def parse_markup(
    text: str, *, mode: FrameMode = Mode.HOLD, position: Position = Position.FILL
) -> Message:
    """Read markup into a Message.

    Each ``{frame MODE [POSITION]}`` token starts a new Frame. MODE is a Mode
    (``rotate``), ``special`` and a Special Mode (``special snow``), or ``graphic``
    and a Special Graphic (``graphic fireworks``). POSITION defaults to ``fill``. A
    bare ``{frame}`` has no Mode Field, which only the first Frame may lack.

    Args:
        text: The markup.
        mode: The Mode of content before the first ``{frame}`` token.
        position: The Display Position of content before the first ``{frame}``
            token.

    Returns:
        The Message, with one Frame for each ``{frame}`` token, plus one for any
        content before the first.

    Raises:
        MarkupError: The markup can't be read: an unknown token or value, an
            unclosed ``{`` or a stray ``}``, a character that is not printable
            ASCII, or a Frame after the first with no Mode.

    Examples:
        >>> from alpha_led_sign import parse_markup
        >>> message = parse_markup("{frame rotate top}Hi{frame hold bottom}{time}")
        >>> [(frame.mode.name, frame.position.name) for frame in message.frames]
        [('ROTATE', 'TOP'), ('HOLD', 'BOTTOM')]
    """
    frames: list[tuple[FrameMode, Position, list[Segment], int]] = []
    lead: list[Segment] = []
    for item in _scan(text):
        if isinstance(item, _Token) and item.kind == "frame":
            frames.append((*_frame_mode(item), [], item.position))
        else:
            segment = _segment(item) if isinstance(item, _Token) else item
            (frames[-1][2] if frames else lead).append(segment)
    if lead or not frames:
        frames.insert(0, (mode, position, lead, 0))
    built: list[Frame] = []
    for index, (frame_mode, frame_position, segments, at) in enumerate(frames):
        if index and frame_mode is None:
            raise MarkupError("only the first Frame may have no Mode: give {frame} a Mode", at)
        try:
            built.append(Frame(frame_mode, frame_position, segments))
        except ValueError as error:
            raise MarkupError(str(error), at) from error
    return Message(*built)


def _frame_mode(token: "_Token") -> tuple[FrameMode, Position]:
    values = list(token.values)
    if not values:
        return None, Position.FILL
    first = values.pop(0)
    frame_mode: FrameMode
    if first.lower() in ("special", "graphic"):
        if not values:
            raise MarkupError(f"{{frame {first}}} needs a name", token.position)
        enum = SpecialMode if first.lower() == "special" else SpecialGraphic
        frame_mode = _member(enum, first.lower(), values.pop(0), token.position)
    else:
        frame_mode = _member(Mode, "mode", first, token.position)
    if len(values) > 1:
        raise MarkupError("{frame} takes a Mode and a Display Position", token.position)
    frame_position = (
        _member(Position, "position", values[0], token.position) if values else Position.FILL
    )
    return frame_mode, frame_position


# Scanning


@dataclass(frozen=True)
class _Token:
    kind: str
    values: tuple[str, ...]
    position: int


def _scan(text: str) -> Iterator[str | _Token]:
    """Split markup into literal text and tokens.

    Yields:
        Each run of literal text, and each token.

    Raises:
        MarkupError: A brace is unclosed or stray, a token is empty, or a character
            is not printable ASCII.
    """
    literal = ""
    i = 0
    while i < len(text):
        char = text[i]
        if char == "{" and text.startswith("{{", i):
            literal, i = literal + "{", i + 2
        elif char == "}" and text.startswith("}}", i):
            literal, i = literal + "}", i + 2
        elif char == "{":
            end = text.find("}", i)
            if end < 0:
                raise MarkupError("unclosed { (write {{ for a literal brace)", i)
            if literal:
                yield literal
            literal = ""
            words = text[i + 1 : end].split()
            if not words:
                raise MarkupError("empty token {}", i)
            yield _Token(words[0].lower(), tuple(words[1:]), i)
            i = end + 1
        elif char == "}":
            raise MarkupError("stray } (write }} for a literal brace)", i)
        elif not (0x20 <= ord(char) <= 0x7E):
            hint = " (use {new_line} for a new line)" if char == "\n" else ""
            raise MarkupError(f"{char!r} is not printable ASCII{hint}", i)
        else:
            literal, i = literal + char, i + 1
    if literal:
        yield literal


# Segment tokens


_ENUMS: dict[str, type[Enum]] = {
    "color": Color,
    "font": Font,
    "speed": Speed,
    "spacing": Spacing,
}

type _Switch = type[Wide] | type[DoubleHigh] | type[TrueDescenders] | type[CharacterFlash]
type _Reference = type[StringRef] | type[DotsPictureRef]

_SWITCH_KINDS: dict[_Switch, str] = {
    Wide: "wide",
    DoubleHigh: "double_high",
    TrueDescenders: "descenders",
    CharacterFlash: "flash",
}
_SWITCHES: dict[str, Callable[[bool], Segment]] = {k: t for t, k in _SWITCH_KINDS.items()}

_LABEL_KINDS: dict[_Reference, str] = {StringRef: "string", DotsPictureRef: "picture"}
_LABELS: dict[str, Callable[[str], Segment]] = {k: t for t, k in _LABEL_KINDS.items()}

_BARE: dict[str, Segment] = {
    "time": CurrentTime(),
    **{member.name.lower(): member for member in Control},
}


def _value_name(member: Enum, kind: str) -> str:
    """Spell an enum member as markup does.

    Returns:
        The member's name in lowercase, without ``kind_``.
    """
    return member.name.lower().removeprefix(f"{kind}_")


def _member[E: Enum](enum: type[E], kind: str, value: str, position: int) -> E:
    for member in enum:
        if _value_name(member, kind) == value.lower():
            return member
    known = ", ".join(_value_name(member, kind) for member in enum)
    raise MarkupError(f"{value!r} is not a {kind}; one of: {known}", position)


def _switch(token: _Token, values: tuple[str, ...]) -> bool:
    match [value.lower() for value in values]:
        case [] | ["on"]:
            return True
        case ["off"]:
            return False
        case _:
            raise MarkupError(f"{{{token.kind}}} takes on or off", token.position)


def _one(token: _Token) -> str:
    if len(token.values) != 1:
        raise MarkupError(f"{{{token.kind}}} takes one value", token.position)
    return token.values[0]


def _segment(token: _Token) -> Segment:
    kind, values, position = token.kind, token.values, token.position
    if kind in _BARE:
        if values:
            raise MarkupError(f"{{{kind}}} takes no value", position)
        return _BARE[kind]
    if kind in _ENUMS:
        # Every enum in _ENUMS is a Control Code (it has encode()).
        return cast("Segment", _member(_ENUMS[kind], kind, _one(token), position))
    if kind in _SWITCHES:
        return _SWITCHES[kind](_switch(token, values))
    if kind == "date":
        if not values:
            return CurrentDate()
        return CurrentDate(_member(DateFormat, kind, _one(token), position))
    if kind == "attribute":
        if not values:
            raise MarkupError("{attribute} takes an attribute and on or off", position)
        return CharacterAttribute(
            _member(Attribute, kind, values[0], position), _switch(token, values[1:])
        )
    if kind in _LABELS:
        try:
            return _LABELS[kind](_one(token))
        except MarkupError:
            raise
        except ValueError as error:
            raise MarkupError(str(error), position) from error
    if kind == "raw":
        try:
            return RawControl(bytes.fromhex(_one(token)))
        except MarkupError:
            raise
        except ValueError as error:
            raise MarkupError(f"{{raw}} takes hex digits: {error}", position) from error
    raise MarkupError(f"unknown token {{{kind}}}", position)


# Rendering


def to_markup(content: Message | Frame | Sequence[Segment]) -> str:
    """Write content as markup.

    Reading the result back with ``parse_markup`` (or ``parse_segments``) gives the
    same content. Every Frame starts with its ``{frame}`` token, so reading back needs
    no defaults. A Control Code without a spelling is written as ``{raw HEX}``.

    Args:
        content: A Message, one Frame, or a sequence of Segments.

    Returns:
        The markup.

    Examples:
        >>> from alpha_led_sign import Color, Frame, Mode, Position, to_markup
        >>> to_markup(Frame(Mode.ROTATE, Position.TOP, [Color.RED, "Hi {there}"]))
        '{frame rotate top}{color red}Hi {{there}}'
    """
    if isinstance(content, Message):
        return "".join(_render_frame(frame) for frame in content.frames)
    if isinstance(content, Frame):
        return _render_frame(content)
    return "".join(_render_segment(segment) for segment in content)


def _render_frame(frame: Frame) -> str:
    position = _value_name(frame.position, "position")
    match frame.mode:
        case None:
            head = "{frame}"
        case SpecialMode():
            head = f"{{frame special {_value_name(frame.mode, 'special')} {position}}}"
        case SpecialGraphic():
            head = f"{{frame graphic {_value_name(frame.mode, 'graphic')} {position}}}"
        case _:
            head = f"{{frame {_value_name(frame.mode, 'mode')} {position}}}"
    return head + "".join(_render_segment(segment) for segment in frame.content)


_ENUM_KINDS = {enum: kind for kind, enum in _ENUMS.items()}
# File Labels a token can't hold: "}" would end it, and a space would split it.
_UNSPELLABLE_LABELS = frozenset("} ")


def _render_segment(segment: Segment) -> str:
    match segment:
        case str():
            return escape_markup(segment)
        case Control():
            return f"{{{segment.name.lower()}}}"
        case CurrentTime():
            return "{time}"
        case CurrentDate():
            return f"{{date {_value_name(segment.format, 'date')}}}"
        case CharacterAttribute():
            state = "on" if segment.on else "off"
            return f"{{attribute {_value_name(segment.attribute, 'attribute')} {state}}}"
        case Wide() | DoubleHigh() | TrueDescenders() | CharacterFlash():
            return f"{{{_SWITCH_KINDS[type(segment)]} {'on' if segment.on else 'off'}}}"
        case StringRef() | DotsPictureRef() if segment.label not in _UNSPELLABLE_LABELS:
            return f"{{{_LABEL_KINDS[type(segment)]} {segment.label}}}"
        case Enum() if type(segment) in _ENUM_KINDS:
            kind = _ENUM_KINDS[type(segment)]
            return f"{{{kind} {_value_name(segment, kind)}}}"
        case _:
            return f"{{raw {segment.encode().hex().upper()}}}"


__all__ = ["MarkupError", "escape_markup", "parse_markup", "parse_segments", "to_markup"]
