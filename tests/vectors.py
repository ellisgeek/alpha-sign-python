"""Byte vectors from the manual that more than one test file uses."""

TABLE_41 = b"\x00\x00\x00\x00\x00\x01Z00\x02AAHELLO\x0301FB\x04"
"""Table 41, p. 60: "AAHELLO" to Sign Type Z, address 00, with Checksum 01FB.

Five NULs, <SOH>"Z00"<STX>"AAHELLO"<ETX>"01FB"<EOT>: a TEXT File "A" write of HELLO
with no Mode Field, to every Sign.
"""
