"""Markup: a string spelling of Messages, Frames, and Segments (.scratch/markup/spec.md)."""

import pytest

from alpha_led_sign.markup import (
    MarkupError,
    escape_markup,
    parse_markup,
    parse_segments,
    to_markup,
)
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
from alpha_led_sign.protocol.message import Frame, Message, Segment, decode_message, encode_content


def test_text_without_tokens_is_literal() -> None:
    assert parse_segments("Hello, world") == ("Hello, world",)


@pytest.mark.parametrize(
    ("markup", "segment"),
    [
        ("{color red}", Color.RED),
        ("{color dim_green}", Color.DIM_GREEN),
        ("{color rainbow_1}", Color.RAINBOW_1),
        ("{font seven_high}", Font.SEVEN_HIGH),
        ("{speed 3}", Speed.SPEED_3),
        ("{speed no_hold}", Speed.NO_HOLD),
        ("{spacing fixed_width}", Spacing.FIXED_WIDTH),
        ("{date mmm_dd_yyyy}", CurrentDate(DateFormat.MMM_DD_YYYY)),
        ("{time}", CurrentTime()),
        ("{new_line}", Control.NEW_LINE),
        ("{new_page}", Control.NEW_PAGE),
        ("{wide on}", Wide(True)),
        ("{wide off}", Wide(False)),
        ("{wide}", Wide(True)),
        ("{double_high on}", DoubleHigh(True)),
        ("{descenders off}", TrueDescenders(False)),
        ("{flash on}", CharacterFlash(True)),
        ("{attribute shadow on}", CharacterAttribute(Attribute.SHADOW, True)),
        ("{attribute double_wide off}", CharacterAttribute(Attribute.DOUBLE_WIDE, False)),
        ("{string T}", StringRef("T")),
        ("{picture A}", DotsPictureRef("A")),
        ("{raw 1F4142}", RawControl(b"\x1fAB")),
    ],
)
def test_each_token_is_one_segment(markup: str, segment: object) -> None:
    assert parse_segments(markup) == (segment,)


def test_tokens_and_text_mix() -> None:
    segments = parse_segments("{color amber}Temp: {string T}F{new_line}{time}")

    assert segments == (
        Color.AMBER,
        "Temp: ",
        StringRef("T"),
        "F",
        Control.NEW_LINE,
        CurrentTime(),
    )


def test_markup_encodes_to_the_appendix_g_bytes() -> None:
    # Appendix G, pp. 81-82: 1CH "1" red, 1AH "3" seven high, 10H + label.
    segments = parse_segments("{color red}{font seven_high}T={string T}")

    assert encode_content(segments) == b"\x1c1\x1a3T=\x10T"


def test_names_and_values_ignore_case_but_labels_do_not() -> None:
    assert parse_segments("{COLOR Red}{String t}") == (Color.RED, StringRef("t"))


def test_doubled_braces_are_literal_braces() -> None:
    assert parse_segments("{{x}} = {color red}1") == ("{x} = ", Color.RED, "1")


@pytest.mark.parametrize(
    ("markup", "position", "match"),
    [
        ("ab{blink}", 2, "unknown"),
        ("{color mauve}", 0, "mauve"),
        ("x{color}", 1, "color"),
        ("{wide sideways}", 0, "on or off"),
        ("{string TT}", 0, "File Label"),
        ("{raw zz}", 0, "hex"),
        ("{time now}", 0, "time"),
        ("ok {color red", 3, "unclosed"),
        ("ok } no", 3, "stray"),
        ("{}", 0, "empty"),
    ],
)
def test_bad_markup_names_where_it_went_wrong(markup: str, position: int, match: str) -> None:
    with pytest.raises(MarkupError, match=match) as raised:
        parse_segments(markup)

    assert raised.value.position == position
    assert isinstance(raised.value, ValueError)


def test_escaped_text_reads_back_as_itself() -> None:
    outside = "{color red} is not a token}{"

    assert parse_segments(escape_markup(outside)) == (outside,)


# Frames


def test_a_frame_token_matches_table_47() -> None:
    # Table 47, p. 65: <ESC> "&" (bottom line) "a" (ROTATE) "HELLO".
    assert parse_markup("{frame rotate bottom}HELLO").encode() == b"\x1b&aHELLO"


def test_special_modes_and_graphics_match_table_48() -> None:
    # Table 48, pp. 65-66: SNOW on the top line, an empty ROTATE, then WELCOME.
    message = parse_markup(
        "{frame special snow top}Hello There{frame rotate top}{frame special welcome bottom}"
    )

    assert message.encode() == b'\x1b"n2Hello There\x1b"a\x1b&n8'


def test_a_special_graphic_frame() -> None:
    message = parse_markup("{frame graphic fireworks}{frame hold}Bang")

    assert message == Message(
        Frame(SpecialGraphic.FIREWORKS), Frame(Mode.HOLD, Position.FILL, "Bang")
    )


def test_content_before_any_frame_token_takes_the_callers_mode_and_position() -> None:
    assert parse_markup("Hi") == Message(Frame(Mode.HOLD, Position.FILL, "Hi"))
    assert parse_markup("Hi{frame wipe_up}there", mode=Mode.ROTATE, position=Position.TOP) == (
        Message(
            Frame(Mode.ROTATE, Position.TOP, "Hi"),
            Frame(Mode.WIPE_UP, Position.FILL, "there"),
        )
    )


def test_empty_markup_is_one_empty_frame() -> None:
    assert parse_markup("") == Message(Frame(Mode.HOLD, Position.FILL))


def test_a_bare_frame_token_has_no_mode_field() -> None:
    # Table 41, p. 60: "HELLO" with no Mode Field.
    assert parse_markup("{frame}HELLO").encode() == b"HELLO"


@pytest.mark.parametrize(
    ("markup", "position", "match"),
    [
        ("{frame sideways}", 0, "sideways"),
        ("{frame special}", 0, "special"),
        ("{frame hold diagonal}", 0, "diagonal"),
        ("{frame hold top extra}", 0, "frame"),
        ("x{frame hold}{frame}", 13, "first Frame"),
        ("{frame graphic thank_you}words", 0, "Special Graphic"),
    ],
)
def test_bad_frame_tokens_say_where(markup: str, position: int, match: str) -> None:
    with pytest.raises(MarkupError, match=match) as raised:
        parse_markup(markup)

    assert raised.value.position == position


def test_frames_are_refused_where_only_segments_go() -> None:
    with pytest.raises(MarkupError, match="frame") as raised:
        parse_segments("ab{frame hold}")

    assert raised.value.position == 2


# Rendering


def test_segments_render_as_markup() -> None:
    segments = [Color.RED, "Hi {x}", StringRef("T"), Wide(False), Speed.SPEED_2, CurrentDate()]

    assert to_markup(segments) == (
        "{color red}Hi {{x}}{string T}{wide off}{speed 2}{date mm_dd_yy_slash}"
    )


def test_a_message_renders_each_frame() -> None:
    message = Message(
        Frame(None, content="lead"),
        Frame(SpecialMode.SNOW, Position.TOP, "Hello"),
        Frame(SpecialGraphic.FIREWORKS, Position.BOTTOM),
        Frame(Mode.HOLD, Position.FILL, [CharacterAttribute(Attribute.FANCY, True)]),
    )

    assert to_markup(message) == (
        "{frame}lead{frame special snow top}Hello{frame graphic fireworks bottom}"
        "{frame hold fill}{attribute fancy on}"
    )


def test_unmodeled_bytes_render_as_raw() -> None:
    assert to_markup([RawControl(b"\x1fAB")]) == "{raw 1F4142}"


def test_a_label_markup_cannot_spell_renders_as_raw() -> None:
    # "}" can't sit inside a token, so the reference is kept as its bytes (p. 81).
    assert to_markup([StringRef("}")]) == "{raw 107D}"


def test_a_read_message_round_trips_through_markup() -> None:
    # Table 48, pp. 65-66, as a read would decode it.
    message = decode_message(b'\x1b"n2Hello There\x1b"a\x1b&n8')

    assert parse_markup(to_markup(message)) == message


EVERY_SEGMENT = [
    *Color,
    *Font,
    *Speed,
    *Spacing,
    *Control,
    *(CurrentDate(format) for format in DateFormat),
    *(CharacterAttribute(attribute, on) for attribute in Attribute for on in (True, False)),
    *(
        kind(on)
        for kind in (Wide, DoubleHigh, TrueDescenders, CharacterFlash)
        for on in (True, False)
    ),
    CurrentTime(),
    StringRef("a"),
    DotsPictureRef("Z"),
    RawControl(b"\x08\x30"),
    "plain {braces}",
]


@pytest.mark.parametrize("segment", EVERY_SEGMENT, ids=repr)
def test_every_segment_round_trips(segment: Segment) -> None:
    assert parse_segments(to_markup([segment])) == (segment,)


EVERY_FRAME_MODE = [*Mode, *SpecialMode, *SpecialGraphic]


@pytest.mark.parametrize("mode", EVERY_FRAME_MODE, ids=repr)
@pytest.mark.parametrize("position", list(Position), ids=repr)
def test_every_frame_mode_and_position_round_trips(
    mode: Mode | SpecialMode | SpecialGraphic, position: Position
) -> None:
    message = Message(Frame(mode, position))

    assert parse_markup(to_markup(message)) == message
