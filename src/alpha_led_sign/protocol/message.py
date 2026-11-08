"""Messages and Frames: the content of a TEXT File (Table 12, p. 18)."""

from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field

from alpha_led_sign.protocol.codes import ControlCode, Mode, Position, SpecialGraphic, SpecialMode

ESC = b"\x1b"

type Segment = str | ControlCode
"""A piece of Frame content: literal text, or a Control Code."""


@dataclass(frozen=True)
class Frame:
    """One part of a Message, shown with a single Mode and Display Position."""

    mode: Mode | SpecialMode | SpecialGraphic
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
        """The Mode, Display Position, and Control Codes this Frame uses."""
        yield self.mode
        yield self.position
        yield from (segment for segment in self.content if not isinstance(segment, str))

    def encode(self) -> bytes:
        mode_field = ESC + (self.position.value + self.mode.field).encode("ascii")
        return mode_field + encode_content(self.content)


@dataclass(frozen=True, init=False)
class Message:
    """The content of a TEXT File: Frames shown in sequence."""

    frames: tuple[Frame, ...]

    def __init__(self, *frames: Frame) -> None:
        object.__setattr__(self, "frames", frames)

    def codes(self) -> Iterator[object]:
        """Every Mode, Display Position, and Control Code in the Message."""
        for frame in self.frames:
            yield from frame.codes()

    def encode(self) -> bytes:
        return b"".join(frame.encode() for frame in self.frames)


def normalize_content(content: str | Sequence[Segment]) -> tuple[Segment, ...]:
    """Turn content into a tuple of segments, checking that literal text is displayable.

    A lone string is one segment, not a sequence of one-character segments.
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
    """Encode literal text and Control Codes, in order."""
    return b"".join(
        segment.encode("ascii") if isinstance(segment, str) else segment.encode()
        for segment in segments
    )


def _is_displayable(text: str) -> bool:
    """True if every character is in the standard character set (Appendix G, p. 83)."""
    return all(0x20 <= ord(char) <= 0x7F for char in text)
