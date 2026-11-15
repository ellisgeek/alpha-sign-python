"""Messages and Frames: the content of a TEXT File (Table 12, p. 18)."""

from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field

from alpha_led_sign.protocol.codes import (
    SPECIAL,
    ControlCode,
    Mode,
    Position,
    RawControl,
    SpecialGraphic,
    SpecialMode,
)
from alpha_led_sign.protocol.control_codes import decode_control

ESC = b"\x1b"

type Segment = str | ControlCode
"""A piece of Frame content: literal text, or a Control Code."""


@dataclass(frozen=True)
class Frame:
    r"""One part of a Message, shown with a single Mode and Display Position.

    Attributes:
        mode: How the Frame is shown. None means no Mode Field, so the Sign picks.
            Only the first Frame of a Message may have None.
        position: Which lines the Frame uses.
        content: Literal text and Control Codes, in order. A lone string is one
            Segment.

    Raises:
        ValueError: The text is not printable ASCII, or a Frame with a Special
            Graphic has content.

    Examples:
        >>> from alpha_led_sign import Color, Frame, Mode, Position
        >>> Frame(Mode.ROTATE, Position.TOP, [Color.RED, "Hello"]).encode()
        b'\x1b"a\x1c1Hello'
    """

    mode: Mode | SpecialMode | SpecialGraphic | None
    position: Position = Position.FILL
    content: Sequence[Segment] = field(default=())

    def __post_init__(self) -> None:
        content = normalize_content(self.content)
        object.__setattr__(self, "content", content)
        if isinstance(self.mode, SpecialGraphic) and content:
            raise ValueError(
                "a Frame with a Special Graphic cannot show text; put it in the next Frame"
            )

    def codes(self) -> Iterator[object]:
        """List the Mode, Display Position, and Control Codes this Frame uses.

        Yields:
            The Mode and Display Position when there is a Mode Field, then each
            Control Code in the content.
        """
        if self.mode is not None:
            yield self.mode
            yield self.position
        yield from (segment for segment in self.content if not isinstance(segment, str))

    def encode(self) -> bytes:
        """Encode the Mode Field and the content.

        Returns:
            The Frame as it appears in TEXT File data.
        """
        if self.mode is None:
            return encode_content(self.content)
        mode_field = ESC + (self.position.value + self.mode.field).encode("ascii")
        return mode_field + encode_content(self.content)


@dataclass(frozen=True, init=False)
class Message:
    """The content of a TEXT File: Frames shown in sequence.

    Args:
        *frames: The Frames, in order. A Message with none is empty.

    Attributes:
        frames: The Frames, in order.

    Raises:
        ValueError: A Frame after the first has no Mode.
    """

    frames: tuple[Frame, ...]

    def __init__(self, *frames: Frame) -> None:
        if any(frame.mode is None for frame in frames[1:]):
            raise ValueError("only the first Frame of a Message may have no Mode")
        object.__setattr__(self, "frames", frames)

    def codes(self) -> Iterator[object]:
        """List every Mode, Display Position, and Control Code in the Message.

        Yields:
            The codes of each Frame, in order.
        """
        for frame in self.frames:
            yield from frame.codes()

    def encode(self) -> bytes:
        """Encode the Frames.

        Returns:
            The TEXT File data.
        """
        return b"".join(frame.encode() for frame in self.frames)


def normalize_content(content: str | Sequence[Segment]) -> tuple[Segment, ...]:
    """Turn content into a tuple of Segments, checking that literal text is displayable.

    Args:
        content: A string, or a sequence of Segments. A lone string is one Segment,
            not a sequence of one-character Segments.

    Returns:
        The Segments.

    Raises:
        ValueError: Literal text has a character outside 20H-7FH.
    """
    segments = (content,) if isinstance(content, str) else tuple(content)
    for segment in segments:
        if isinstance(segment, str) and not _is_displayable(segment):
            raise ValueError(
                f"literal text must be printable ASCII (20H-7FH), got {segment!r}; "
                "use Control Codes such as Control.NEW_LINE for layout"
            )
    return segments


def encode_content(segments: Sequence[Segment]) -> bytes:
    """Encode literal text and Control Codes, in order.

    Args:
        segments: The Segments.

    Returns:
        The bytes.
    """
    return b"".join(
        segment.encode("ascii") if isinstance(segment, str) else segment.encode()
        for segment in segments
    )


def _is_displayable(text: str) -> bool:
    """Check that text is in the standard character set (Appendix G, p. 83).

    Returns:
        True if every character is in it.
    """
    return all(0x20 <= ord(char) <= 0x7F for char in text)


def decode_content(data: bytes) -> tuple[Segment, ...]:
    """Decode literal text and Control Codes with no Mode Fields, such as STRING File data.

    Args:
        data: The bytes.

    Returns:
        The Segments, in order.

    Raises:
        ValueError: The data has a Mode Field.
    """
    message = decode_message(data)
    if not message.frames:
        return ()
    (frame,) = message.frames
    if frame.mode is not None:
        raise ValueError(f"expected content without a Mode Field, got {data!r}")
    return tuple(frame.content)


def decode_message(data: bytes) -> Message:
    """Decode TEXT File data, as a Sign sends it back, into a Message.

    Args:
        data: The bytes.

    Returns:
        The Message, with a Frame for each Mode Field.

    Raises:
        ValueError: A Mode Field is cut short or has an unknown code.
    """
    frames: list[Frame] = []
    mode: Mode | SpecialMode | SpecialGraphic | None = None
    position = Position.FILL
    segments: list[Segment] = []
    text = bytearray()

    def flush_text() -> None:
        if text:
            segments.append(text.decode("ascii"))
            text.clear()

    index = 0
    while index < len(data):
        byte = data[index]
        if byte == ESC[0]:
            flush_text()
            if mode is not None or segments:
                frames.append(Frame(mode, position, segments))
            mode, position, index = _decode_mode_field(data, index)
            segments = []
        elif 0x20 <= byte <= 0x7F:
            text.append(byte)
            index += 1
        elif byte < 0x20:
            flush_text()
            code, index = decode_control(data, index)
            segments.append(code)
        else:  # outside the standard character set
            flush_text()
            segments.append(RawControl(bytes([byte])))
            index += 1
    flush_text()
    if mode is not None or segments:
        frames.append(Frame(mode, position, segments))
    return Message(*frames)


def _decode_mode_field(
    data: bytes, start: int
) -> tuple[Mode | SpecialMode | SpecialGraphic, Position, int]:
    """Decode ESC, Display Position, Mode Code, and any Special Specifier.

    Returns:
        The Mode, the Display Position, and the index after the Mode Field.

    Raises:
        ValueError: The Mode Field is cut short or has an unknown code.
    """
    field = data[start + 1 : start + 4].decode("ascii", errors="replace")
    if len(field) < 2:
        raise ValueError(f"truncated Mode Field at byte {start}: {data[start:]!r}")
    position = Position(field[0])
    if field[1] != SPECIAL:
        return Mode(field[1]), position, start + 3
    specifier = field[2:3]
    graphics = {graphic.value for graphic in SpecialGraphic}
    special = SpecialGraphic(specifier) if specifier in graphics else SpecialMode(specifier)
    return special, position, start + 4
