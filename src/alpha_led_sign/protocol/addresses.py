"""Sign Addresses: which Sign of a Sign Type acts on a Packet (p. 11)."""


def check_sign_address(address: int, *, name: str = "a Sign Address") -> None:
    """Check that a Sign Address is 0-255, which two hex digits can hold.

    Address 0 is the broadcast address.

    Args:
        address: The Sign Address.
        name: What the error message calls the value, such as ``"max_address"``.

    Raises:
        ValueError: ``address`` is not 0-255.
    """
    if not 0 <= address <= 0xFF:
        raise ValueError(f"{name} must be 0-255, got {address}")
