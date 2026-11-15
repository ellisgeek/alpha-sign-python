"""The bytes that frame a Packet or a Response (pp. 10-14), and the Checksum."""

NUL = b"\x00"
SOH = b"\x01"
STX = b"\x02"
ETX = b"\x03"
EOT = b"\x04"
FRAMING_BYTES = frozenset(SOH + STX + ETX + EOT)
SYNC = NUL * 5


def compute_checksum(data: bytes) -> int:
    r"""Compute a Checksum (p. 12).

    Args:
        data: The bytes from an STX through its ETX, both included.

    Returns:
        The 16-bit sum of the bytes.

    Examples:
        >>> from alpha_led_sign.protocol import compute_checksum
        >>> f"{compute_checksum(b'\x02AAHELLO\x03'):04X}"
        '01FB'
    """
    return sum(data) & 0xFFFF
