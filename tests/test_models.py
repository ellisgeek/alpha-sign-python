"""Sign Models: profiles from the manual and brochure, and validation against them."""

import warnings
from dataclasses import replace

import pytest

from alpha_led_sign import models
from alpha_led_sign.models import (
    Capability,
    UnsupportedCapability,
    UnsupportedCapabilityWarning,
    validate,
)
from alpha_led_sign.protocol.codes import (
    Color,
    Control,
    ControlCode,
    CurrentTime,
    DoubleHigh,
    Font,
    Mode,
    Position,
    SpecialGraphic,
    SpecialMode,
    StringRef,
)
from alpha_led_sign.protocol.commands import SetMemoryConfiguration, WriteString, WriteText
from alpha_led_sign.protocol.memory import DotsPictureFile, StringFile, TextFile
from alpha_led_sign.protocol.message import Frame, Message
from alpha_led_sign.protocol.versions import ProtocolVersion


def test_4120c_profile_matches_table_5_table_3_and_the_brochure() -> None:
    model = models.ALPHA_4120C

    assert model.name == "4120C"
    assert model.sign_type == "a"
    assert (model.columns, model.rows, model.lines) == (120, 16, 2)
    assert model.memory_bytes == 28_000
    assert model.max_messages == 81
    assert model.protocol_versions == {ProtocolVersion.EZ_KEY_II, ProtocolVersion.ALPHA_1_0}


def test_4120c_capabilities_come_from_the_4000_series_rows_of_tables_68_to_70() -> None:
    capabilities = models.ALPHA_4120C.capabilities
    assert capabilities is not None

    assert {Capability.SNOW, Capability.ROTATE, Capability.COLOR, Capability.TIME} <= capabilities
    assert {Capability.FONT_FULL_HEIGHT, Capability.STRING, Capability.ANIMATION} <= capabilities
    assert Capability.COMPRESSED_ROTATE not in capabilities  # Table 68
    assert Capability.DOUBLE_HIGH not in capabilities  # Table 69
    assert Capability.NEW_PAGE not in capabilities  # Table 70


@pytest.mark.parametrize(
    ("name", "sign_type", "columns"),
    [
        ("4080C", "t", 80),
        ("4120C", "a", 120),
        ("4120R", "g", 120),
        ("4160C", "b", 160),
        ("4160R", "h", 160),
        ("4200C", "c", 200),
        ("4200R", "i", 200),
        ("4240C", "d", 240),
        ("4240R", "j", 240),
    ],
)
def test_4000_series_models_match_table_5_and_the_brochure(
    name: str, sign_type: str, columns: int
) -> None:
    model = models.get(name)

    assert (model.name, model.sign_type, model.columns, model.rows) == (
        name,
        sign_type,
        columns,
        16,
    )
    assert (model.lines, model.memory_bytes, model.max_messages) == (2, 28_000, 81)
    assert model.series == "4000 Series"


def test_red_4000_series_models_have_no_color_but_tricolor_ones_do() -> None:
    # Table 69, note 1: models ending in R display red only.
    assert Capability.COLOR not in (models.get("4120R").capabilities or ())
    assert Capability.COLOR in (models.get("4120C").capabilities or ())


def test_betabrite_uses_its_own_rows_of_the_matrices() -> None:
    model = models.BETABRITE
    capabilities = model.capabilities or frozenset()

    assert model.sign_type == "^"  # Table 5
    assert Capability.COMPRESSED_ROTATE in capabilities  # Table 68
    assert Capability.COUNTER not in capabilities  # Table 70


def test_generic_model_reaches_every_sign_and_skips_capability_checks() -> None:
    assert models.GENERIC.sign_type == "Z"
    assert models.GENERIC.protocol_versions == {ProtocolVersion.ALPHA_1_0}
    assert models.GENERIC.capabilities is None


def test_unknown_model_names_raise_a_helpful_error() -> None:
    with pytest.raises(KeyError, match="4120C"):
        models.get("9999X")


def test_a_sign_type_finds_the_one_model_that_has_it() -> None:
    # Table 5, p. 10: "a" is the 4120C, "^" the BetaBrite; "!" is no Sign Type.
    assert models.by_sign_type("a") is models.ALPHA_4120C
    assert models.by_sign_type("^") is models.BETABRITE
    assert models.by_sign_type("!") is None


def test_a_sign_type_that_several_models_share_finds_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    twin = replace(models.ALPHA_4120C, name="4120C twin")
    monkeypatch.setitem(models.REGISTRY, twin.name, twin)
    assert models.by_sign_type("a") is None


def write(*frames: Frame) -> WriteText:
    return WriteText("A", Message(*frames))


def test_a_message_the_4120c_supports_passes_without_warnings() -> None:
    command = write(
        Frame(
            SpecialMode.SNOW, Position.TOP, [Color.RED, Font.SEVEN_HIGH, "Temp: ", StringRef("T")]
        ),
        Frame(Mode.HOLD, Position.BOTTOM, [Color.GREEN, CurrentTime()]),
        Frame(SpecialGraphic.FIREWORKS),
    )

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        validate(models.ALPHA_4120C, [command], strict=True)
        validate(models.ALPHA_4120C, [command])


def test_strict_validation_raises_for_a_mode_the_model_lacks() -> None:
    command = write(Frame(Mode.COMPRESSED_ROTATE, Position.FILL, "hi"))

    with pytest.raises(UnsupportedCapability, match=r"4120C.*compressed rotate"):
        validate(models.ALPHA_4120C, [command], strict=True)


def test_advisory_validation_warns_once_per_problem_and_carries_on() -> None:
    command = write(Frame(Mode.COMPRESSED_ROTATE, Position.FILL, [DoubleHigh(), "hi"]))

    with pytest.warns(UnsupportedCapabilityWarning) as record:
        validate(models.ALPHA_4120C, [command])

    assert len(record) == 2


@pytest.mark.parametrize(
    "code",
    [Control.NEW_PAGE, DoubleHigh(), Font.SEVEN_SHADOW, Font.TEN_HIGH],
)
def test_control_codes_the_4120c_lacks_are_reported(code: ControlCode) -> None:
    # Tables 69-70 (4000 Series row), and Appendix G footnote 1 (BetaBrite 1036 fonts).
    with pytest.raises(UnsupportedCapability):
        validate(models.ALPHA_4120C, [write(Frame(Mode.HOLD, Position.FILL, [code]))], strict=True)


def test_red_models_report_colors() -> None:
    command = write(Frame(Mode.HOLD, Position.FILL, [Color.GREEN, "go"]))

    with pytest.raises(UnsupportedCapability, match="color"):
        validate(models.ALPHA_4120R, [command], strict=True)


@pytest.mark.parametrize(
    "frame",
    [Frame(Mode.EXPLODE, Position.FILL, "x"), Frame(Mode.HOLD, Position.LEFT, "x")],
)
def test_alpha_3_codes_are_reported_even_without_capability_checks(frame: Frame) -> None:
    # Table 65: EXPLODE is Alpha 3.0. Table 12: LEFT/RIGHT positions are Alpha 3.0 only.
    with pytest.raises(UnsupportedCapability, match=r"Alpha 3\.0"):
        validate(models.GENERIC, [write(frame)], strict=True)


def test_generic_model_does_not_check_capabilities() -> None:
    command = write(Frame(Mode.COMPRESSED_ROTATE, Position.FILL, [DoubleHigh(), "hi"]))

    validate(models.GENERIC, [command], strict=True)


def test_string_file_content_is_validated_too() -> None:
    with pytest.raises(UnsupportedCapability, match="color"):
        validate(models.ALPHA_4120R, [WriteString("T", [Color.GREEN, "72"])], strict=True)


def configure(*files: TextFile | StringFile | DotsPictureFile) -> SetMemoryConfiguration:
    return SetMemoryConfiguration(files)


def test_a_memory_configuration_that_fills_the_4120c_exactly_passes() -> None:
    # Table 5 and the brochure: 28,000 bytes. p. 27, note 1: 11 bytes of overhead per File.
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        validate(models.ALPHA_4120C, [configure(TextFile("A", size=27_989))], strict=True)


def test_a_memory_configuration_too_big_for_the_4120c_raises_in_strict_mode() -> None:
    with pytest.raises(UnsupportedCapability, match=r"28,000 bytes.*needs 28,001"):
        validate(models.ALPHA_4120C, [configure(TextFile("A", size=27_990))], strict=True)


def test_a_memory_configuration_too_big_for_the_4120c_warns_otherwise() -> None:
    with pytest.warns(UnsupportedCapabilityWarning, match="memory"):
        validate(models.ALPHA_4120C, [configure(TextFile("A", size=27_990))])


def test_every_file_counts_its_overhead_but_dots_picture_sizes_do_not() -> None:
    # p. 27, note 1 leaves DOTS PICTURE sizes out of the sum; their overhead is counted.
    files = (
        TextFile("A", size=27_966),
        StringFile("T", size=1),
        DotsPictureFile("p", rows=16, columns=120),
    )
    validate(models.ALPHA_4120C, [configure(*files)], strict=True)  # 27,966 + 1 + 3 x 11 = 28,000

    with pytest.raises(UnsupportedCapability, match="memory"):
        validate(
            models.ALPHA_4120C, [configure(TextFile("A", size=27_967), *files[1:])], strict=True
        )


def test_a_last_text_file_of_size_0_counts_only_its_overhead() -> None:
    files = (TextFile("B", size=27_978), TextFile("A", size=0))  # 27,978 + 2 x 11 = 28,000

    validate(models.ALPHA_4120C, [configure(*files)], strict=True)


def test_the_overhead_per_file_is_model_data() -> None:
    model = replace(models.ALPHA_4120C, file_overhead=13)  # the readerboard project's figure

    with pytest.raises(UnsupportedCapability, match="memory"):
        validate(model, [configure(TextFile("A", size=27_989))], strict=True)


def test_memory_is_not_checked_when_the_models_size_is_unknown() -> None:
    validate(models.GENERIC, [configure(TextFile("A", size=0xFFFF))], strict=True)
