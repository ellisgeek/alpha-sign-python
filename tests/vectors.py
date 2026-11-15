"""Byte vectors from the manual that more than one test file uses."""

TABLE_41 = b"\x00\x00\x00\x00\x00\x01Z00\x02AAHELLO\x0301FB\x04"
"""Table 41, p. 60: "AAHELLO" to Sign Type Z, address 00, with Checksum 01FB.

Five NULs, <SOH>"Z00"<STX>"AAHELLO"<ETX>"01FB"<EOT>: a TEXT File "A" write of HELLO
with no Mode Field, to every Sign.
"""

NULS = b"\x00" * 20
"""The 20 NULs a Response starts with (Table 14, p. 19)."""

TABLE_46 = NULS + b"\x01000\x02ACFILE C\x03020C\x04"
"""Table 46: the Response to Read TEXT "C", which holds FILE C."""

TABLE_54 = NULS + b"\x01000\x02E&6\x0300A6\x04"
"""Table 54: the Response to Read day of week: Friday."""

TABLE_59 = NULS + b"\x01000\x02G28,234,000\x030237\x04"
"""Table 59: the Response to Read STRING "2", which holds 8,234,000."""
