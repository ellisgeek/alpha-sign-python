"""Protocol Versions (Table 3, p. 8)."""

from enum import IntEnum


class ProtocolVersion(IntEnum):
    """One revision of the Alpha protocol. Later versions sort higher."""

    EZ_KEY_II = 1
    ALPHA_1_0 = 2
    ALPHA_2_0 = 3
    ALPHA_3_0 = 4

    @property
    def label(self) -> str:
        """The name the manual uses, such as "Alpha 1.0"."""
        return _LABELS[self]


_LABELS = {
    ProtocolVersion.EZ_KEY_II: "EZ KEY II",
    ProtocolVersion.ALPHA_1_0: "Alpha 1.0",
    ProtocolVersion.ALPHA_2_0: "Alpha 2.0",
    ProtocolVersion.ALPHA_3_0: "Alpha 3.0",
}
