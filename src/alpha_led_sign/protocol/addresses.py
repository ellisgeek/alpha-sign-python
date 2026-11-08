"""Sign Addresses: which Sign of a Sign Type acts on a Packet (p. 11)."""


def check_sign_address(address: int, *, name: str = "a Sign Address") -> None:
    """Raise ValueError unless ``address`` is 0-255 (two hex digits; 0 is broadcast).

    ``name`` is what the error message calls the value, such as ``"max_address"``.
    """
    if not 0 <= address <= 0xFF:
        raise ValueError(f"{name} must be 0-255, got {address}")
