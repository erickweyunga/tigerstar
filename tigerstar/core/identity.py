import os

ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def _base58_encode(data: bytes) -> str:
    num = int.from_bytes(data, "big")
    encoded = []
    while num > 0:
        num, remainder = divmod(num, 58)
        encoded.append(ALPHABET[remainder])
    for byte in data:
        if byte == 0:
            encoded.append(ALPHABET[0])
        else:
            break
    return "".join(reversed(encoded))


def generate_id(length: int = 16) -> str:
    raw = os.urandom(length)
    return _base58_encode(raw)
