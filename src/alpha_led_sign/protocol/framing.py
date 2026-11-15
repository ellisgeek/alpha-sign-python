"""The bytes that frame a Packet or a Response (pp. 10-14), and the Checksum."""

NUL = b"\x00"
SOH = b"\x01"
STX = b"\x02"
ETX = b"\x03"
EOT = b"\x04"
FRAMING_BYTES = frozenset(SOH + STX + ETX + EOT)
SYNC = NUL * 5


def compute_checksum(data: bytes) -> int:
    """The 16-bit sum of ``data``, which runs from an STX through its ETX inclusive (p. 12)."""
    return sum(data) & 0xFFFF
