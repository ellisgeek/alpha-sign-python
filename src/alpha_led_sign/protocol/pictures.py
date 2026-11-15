"""DOTS PICTURE content: the pixels of a picture a TEXT File can call (pp. 39-41)."""

import re
from dataclasses import dataclass
from enum import Enum

from alpha_led_sign.protocol.responses import ResponseError


class PixelColor(Enum):
    """One pixel of a SMALL DOTS PICTURE, as its Row Bit Pattern character (p. 40).

    The value is the digit ``DotsPicture.parse`` reads: ``0`` is off, ``1`` is red,
    and so on in the order the members are listed. A red-only model shows only
    ``OFF`` and ``RED``.
    """

    OFF = "0"
    RED = "1"
    GREEN = "2"
    AMBER = "3"
    DIM_RED = "4"
    DIM_GREEN = "5"
    BROWN = "6"
    ORANGE = "7"
    YELLOW = "8"


MAX_HEIGHT = 31
"""Rows in a SMALL DOTS PICTURE (Table 22, p. 39)."""

MAX_WIDTH = 255
"""Columns in a SMALL DOTS PICTURE (Table 22, p. 40)."""


@dataclass(frozen=True)
class DotsPicture:
    """The pixels of a SMALL DOTS PICTURE: rows from top to bottom, each left to right.

    Attributes:
        rows: The rows, each a tuple of pixels. Every row is as wide.

    Raises:
        ValueError: There are more than 31 rows or 255 columns, the rows differ in
            width, or a pixel is not a PixelColor.
    """

    rows: tuple[tuple[PixelColor, ...], ...]

    def __post_init__(self) -> None:
        rows = tuple(tuple(row) for row in self.rows)
        object.__setattr__(self, "rows", rows)
        if len(rows) > MAX_HEIGHT:
            raise ValueError(f"a SMALL DOTS PICTURE has at most {MAX_HEIGHT} rows, got {len(rows)}")
        widths = {len(row) for row in rows}
        if len(widths) > 1:
            raise ValueError(f"every row of a DOTS PICTURE must be as wide; got widths {widths}")
        if self.width > MAX_WIDTH:
            raise ValueError(
                f"a SMALL DOTS PICTURE has at most {MAX_WIDTH} columns, got {self.width}"
            )
        for row in rows:
            for pixel in row:
                if not isinstance(pixel, PixelColor):
                    raise ValueError(f"a DOTS PICTURE pixel must be a PixelColor, got {pixel!r}")

    @classmethod
    def parse(cls, text: str) -> "DotsPicture":
        r"""Build a picture from text, one line per row, in the manual's pixel digits.

        Args:
            text: One line for each row. Each character is a PixelColor digit:
                ``0`` off, ``1`` red, ``2`` green, ``3`` amber, and so on (p. 40).

        Returns:
            The picture.

        Raises:
            ValueError: A character is not a pixel digit, the rows differ in width,
                or the picture is too large.

        Examples:
            >>> from alpha_led_sign import DotsPicture
            >>> arrow = DotsPicture.parse("010\n111\n010")
            >>> arrow.width, arrow.height
            (3, 3)
        """
        return cls(tuple(tuple(PixelColor(char) for char in line) for line in text.splitlines()))

    @property
    def height(self) -> int:
        """The number of rows."""
        return len(self.rows)

    @property
    def width(self) -> int:
        """The number of columns. 0 for a picture with no rows."""
        return len(self.rows[0]) if self.rows else 0


_SIZE = re.compile(rb"[0-9A-Fa-f]{4}")


def decode_dots_picture(data: bytes) -> DotsPicture:
    """Decode DOTS PICTURE File Data (Height, Width, rows; Table 22) as the Sign reads it.

    LF is ignored and the last CR is optional. A short row is padded with off pixels
    and a long one is cut at the Width (p. 40). Rows never sent are off, because the
    Sign clears the picture once it has the Width.

    Args:
        data: The File Data.

    Returns:
        The picture.

    Raises:
        ResponseError: The data does not start with a hex Height and Width, a pixel
            is not a digit, or the picture is too large.
    """
    if not _SIZE.fullmatch(data[:4]):
        raise ResponseError(f"DOTS PICTURE data must start with a hex Height and Width: {data!r}")
    height, width = int(data[:2], 16), int(data[2:4], 16)
    lines = data[4:].replace(b"\n", b"").split(b"\r")
    rows: list[tuple[PixelColor, ...]] = []
    for y in range(height):
        line = lines[y][:width] if y < len(lines) else b""
        try:
            pixels = [PixelColor(chr(byte)) for byte in line]
        except ValueError as error:
            raise ResponseError(f"DOTS PICTURE row {y} has a bad pixel: {line!r}") from error
        rows.append(tuple(pixels) + (PixelColor.OFF,) * (width - len(pixels)))
    try:
        return DotsPicture(tuple(rows))
    except ValueError as error:
        raise ResponseError(str(error)) from error
