"""Control Alpha-protocol LED message signs.

Most callers need only ``Sign`` and the content types re-exported here. The wire
format lives in ``alpha_led_sign.protocol``; Sign Model profiles live in ``models``.
"""

from alpha_led_sign import models
from alpha_led_sign.discovery import DiscoveredSign, discover
from alpha_led_sign.models import SignModel, UnsupportedCapability, UnsupportedCapabilityWarning
from alpha_led_sign.protocol.codes import (
    Attribute,
    CharacterAttribute,
    CharacterFlash,
    Color,
    Control,
    CurrentDate,
    CurrentTime,
    DateFormat,
    DoubleHigh,
    Font,
    Mode,
    Position,
    Spacing,
    SpecialGraphic,
    SpecialMode,
    Speed,
    StringRef,
    TrueDescenders,
    Wide,
)
from alpha_led_sign.protocol.commands import TimeFormat, Tone
from alpha_led_sign.protocol.memory import (
    DotsPictureFile,
    PictureColors,
    RunTime,
    StringFile,
    TextFile,
)
from alpha_led_sign.protocol.message import Frame, Message
from alpha_led_sign.sign import Sign, SignTimeoutError
from alpha_led_sign.transport import SerialFormat, SerialTransport, Transport

__all__ = [
    "Attribute",
    "CharacterAttribute",
    "CharacterFlash",
    "Color",
    "Control",
    "CurrentDate",
    "CurrentTime",
    "DateFormat",
    "DiscoveredSign",
    "DotsPictureFile",
    "DoubleHigh",
    "Font",
    "Frame",
    "Message",
    "Mode",
    "PictureColors",
    "Position",
    "RunTime",
    "SerialFormat",
    "SerialTransport",
    "Sign",
    "SignModel",
    "SignTimeoutError",
    "Spacing",
    "SpecialGraphic",
    "SpecialMode",
    "Speed",
    "StringFile",
    "StringRef",
    "TextFile",
    "TimeFormat",
    "Tone",
    "Transport",
    "TrueDescenders",
    "UnsupportedCapability",
    "UnsupportedCapabilityWarning",
    "Wide",
    "discover",
    "models",
]
