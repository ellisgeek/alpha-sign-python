"""Decoding Response Packets, checked against Appendix F (Tables 46, 54, 59)."""

import pytest

from alpha_led_sign.protocol.packet import ResponseError, ResponseItem, decode_response

NULS = b"\x00" * 20


def test_response_to_read_text_matches_table_46() -> None:
    response = decode_response(NULS + b"\x01000\x02ACFILE C\x03020C\x04")

    assert response == (ResponseItem("A", b"CFILE C"),)


def test_responses_to_read_special_function_and_string_match_tables_54_and_59() -> None:
    assert decode_response(NULS + b"\x01000\x02E&6\x0300A6\x04") == (ResponseItem("E", b"&6"),)
    assert decode_response(NULS + b"\x01000\x02G28,234,000\x030237\x04") == (
        ResponseItem("G", b"28,234,000"),
    )


def test_nested_responses_decode_in_order() -> None:
    # p. 30: a Memory Dump comes back as nested Commands with checksums.
    data = NULS + b"\x01000\x02E&6\x0300A6\x02G28,234,000\x030237\x04"

    assert decode_response(data) == (ResponseItem("E", b"&6"), ResponseItem("G", b"28,234,000"))


def test_a_bad_checksum_is_rejected() -> None:
    with pytest.raises(ResponseError, match="checksum"):
        decode_response(NULS + b"\x01000\x02ACFILE C\x03020D\x04")


@pytest.mark.parametrize(
    "data",
    [
        b"",
        NULS + b"\x01000\x02ACFILE C\x03020C",  # no EOT
        NULS + b"\x01Z00\x02ACFILE C\x03020C\x04",  # not a Response Type Code
        NULS + b"\x01000ACFILE C\x03020C\x04",  # no STX
    ],
)
def test_malformed_responses_are_rejected(data: bytes) -> None:
    with pytest.raises(ResponseError):
        decode_response(data)
