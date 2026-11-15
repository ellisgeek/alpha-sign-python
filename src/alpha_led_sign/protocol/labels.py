"""File Labels: the one-character names of Files (Appendix A, p. 50)."""


def check_file_label(label: str) -> None:
    """Check that a File Label is one printable ASCII character.

    Args:
        label: The File Label.

    Raises:
        ValueError: ``label`` is not one character from 20H to 7EH.
    """
    if len(label) != 1 or not 0x20 <= ord(label) <= 0x7E:
        raise ValueError(f"a File Label is one character from 20H to 7EH, got {label!r}")
