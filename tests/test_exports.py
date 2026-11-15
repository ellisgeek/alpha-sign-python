"""Every public name, pinned, so that removing or renaming an export fails CI.

Adding a name means adding it here too, on purpose.
"""

import importlib

import pytest

PUBLIC = {
    "alpha_led_sign": {
        "Attribute", "CharacterAttribute", "CharacterFlash", "Color", "Control",
        "CurrentDate", "CurrentTime", "DateFormat", "DiscoveredSign", "DotsPicture",
        "DotsPictureFile", "DotsPictureRef", "PixelColor",
        "DoubleHigh", "Font", "Frame", "Message", "Mode", "PictureColors", "Position",
        "RunDay", "RunDays", "RunOrder", "RunTime", "SerialFormat", "SerialTransport",
        "Sign", "SignModel", "SignTimeoutError", "Spacing", "SpecialGraphic",
        "SpecialMode", "Speed", "StringFile", "StringRef", "TextFile", "TimeFormat",
        "Tone", "Transport", "TrueDescenders", "UnsupportedCapability",
        "UnsupportedCapabilityWarning", "Weekday", "Wide", "discover", "models",
    },
    "alpha_led_sign.protocol": {
        "Attribute", "Beep", "Capability", "CharacterAttribute", "CharacterFlash", "Chunk",
        "ClearMemory", "ClearSerialErrorStatus", "Color", "Command", "Control",
        "ControlCode", "CurrentDate", "CurrentTime", "DateFormat", "DotsPicture",
        "DotsPictureFile", "DotsPictureRef", "PixelColor", "ReadDotsPicture",
        "WriteDotsPicture",
        "DoubleHigh", "Font", "Frame", "GeneralInformation", "MemoryFile", "Message",
        "Mode", "NetworkQuery", "NetworkQueryResponse", "PRIORITY_LABEL", "Packet",
        "PictureColors", "Position", "ProgrammableTone", "ProtocolVersion", "RawControl",
        "Read", "ReadDayOfWeek", "ReadGeneralInformation", "ReadSerialErrorStatus",
        "ReadSpecial", "ReadString", "ReadText", "ReceivedResponse", "Recipient",
        "Requirement", "ResponseError", "ResponseItem", "ResponseReader", "RunDay",
        "RunDays", "RunOrder", "RunTime", "Segment", "SerialErrorStatus", "SetDate",
        "SetDayOfWeek", "SetMemoryConfiguration", "SetRunDays", "SetRunSequence",
        "SetRunTimes", "SetSignAddress", "SetSpeaker", "SetTime", "SetTimeFormat",
        "SoftReset", "Spacing", "SpecialFunction", "SpecialGraphic", "SpecialMode",
        "Speed", "StringFile", "StringRef", "TextFile", "TimeFormat", "Tone",
        "TrueDescenders", "UnexpectedResponseError", "Weekday", "Wide", "WriteString",
        "WriteText", "check_file_label", "check_sign_address", "compute_checksum",
        "decode_response", "encode_packet", "lock_byte", "requires",
    },
}  # fmt: skip


@pytest.mark.parametrize("module_name", sorted(PUBLIC))
def test_the_public_names_are_exactly_these(module_name: str) -> None:
    module = importlib.import_module(module_name)

    assert set(module.__all__) == PUBLIC[module_name]


@pytest.mark.parametrize("module_name", sorted(PUBLIC))
def test_every_public_name_resolves(module_name: str) -> None:
    module = importlib.import_module(module_name)

    assert [name for name in PUBLIC[module_name] if not hasattr(module, name)] == []
