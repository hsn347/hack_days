"""Skynet cryptographic primitives matching the game binary (libcocos2dlua.so)."""

import os
import struct
from typing import Tuple

from Crypto.Cipher import DES

# Diffie-Hellman 64-bit modulus (2^64 - 59) and generator (Skynet crypt)
DH_P = 0xFFFFFFFFFFFFFFC5
DH_G = 5

_MD5_K = (
    0xD76AA478, 0xE8C7B756, 0x242070DB, 0xC1BDCEEE,
    0xF57C0FAF, 0x4787C62A, 0xA8304613, 0xFD469501,
    0x698098D8, 0x8B44F7AF, 0xFFFF5BB1, 0x895CD7BE,
    0x6B901122, 0xFD987193, 0xA679438E, 0x49B40821,
    0xF61E2562, 0xC040B340, 0x265E5A51, 0xE9B6C7AA,
    0xD62F105D, 0x02441453, 0xD8A1E681, 0xE7D3FBC8,
    0x21E1CDE6, 0xC33707D6, 0xF4D50D87, 0x455A14ED,
    0xA9E3E905, 0xFCEFA3F8, 0x676F02D9, 0x8D2A4C8A,
    0xFFFA3942, 0x8771F681, 0x6D9D6122, 0xFDE5380C,
    0xA4BEEA44, 0x4BDECFA9, 0xF6BB4B60, 0xBEBFBC70,
    0x289B7EC6, 0xEAA127FA, 0xD4EF3085, 0x04881D05,
    0xD9D4D039, 0xE6DB99E5, 0x1FA27CF8, 0xC4AC5665,
    0xF4292244, 0x432AFF97, 0xAB9423A7, 0xFC93A039,
    0x655B59C3, 0x8F0CCC92, 0xFFEFF47D, 0x85845DD1,
    0x6FA87E4F, 0xFE2CE6E0, 0xA3014314, 0x4E0811A1,
    0xF7537E82, 0xBD3AF235, 0x2AD7D2BB, 0xEB86D391,
)

_MD5_S = (
    7, 12, 17, 22, 7, 12, 17, 22, 7, 12, 17, 22, 7, 12, 17, 22,
    5, 9, 14, 20, 5, 9, 14, 20, 5, 9, 14, 20, 5, 9, 14, 20,
    4, 11, 16, 23, 4, 11, 16, 23, 4, 11, 16, 23, 4, 11, 16, 23,
    6, 10, 15, 21, 6, 10, 15, 21, 6, 10, 15, 21, 6, 10, 15, 21,
)


def random_key() -> bytes:
    """Generate 8 random bytes for a client Diffie-Hellman private key."""
    return os.urandom(8)


def dh_exchange(private_key: bytes) -> bytes:
    """Compute 8-byte little-endian DH public key: G^private mod P."""
    if len(private_key) != 8:
        raise ValueError("private_key must be exactly 8 bytes")
    priv_int = int.from_bytes(private_key, "little")
    pub_int = pow(DH_G, priv_int, DH_P)
    return pub_int.to_bytes(8, "little")


def dh_secret(server_public_key: bytes, private_key: bytes) -> bytes:
    """Compute the shared 8-byte little-endian DH secret."""
    if len(server_public_key) != 8 or len(private_key) != 8:
        raise ValueError("DH keys must be exactly 8 bytes")
    pub_int = int.from_bytes(server_public_key, "little")
    priv_int = int.from_bytes(private_key, "little")
    if pub_int >= DH_P:
        pub_int -= DH_P
    secret_int = pow(pub_int, priv_int, DH_P)
    return secret_int.to_bytes(8, "little")


def _md5_compress_no_add(block64: bytes) -> Tuple[int, int, int, int]:
    """Single-block MD5 compression without final state addition (Skynet hmac64)."""
    words = struct.unpack("<16I", block64)
    a, b, c, d = 0x67452301, 0xEFCDAB89, 0x98BADCFE, 0x10325476

    for i in range(64):
        if i < 16:
            f = (b & c) | (~b & d)
            g = i
        elif i < 32:
            f = (d & b) | (~d & c)
            g = (5 * i + 1) % 16
        elif i < 48:
            f = b ^ c ^ d
            g = (3 * i + 5) % 16
        else:
            f = c ^ (b | ~d)
            g = (7 * i) % 16

        f = (f + a + _MD5_K[i] + words[g]) & 0xFFFFFFFF
        a, d, c = d, c, b
        shift = _MD5_S[i]
        b = (b + (((f << shift) | (f >> (32 - shift))) & 0xFFFFFFFF)) & 0xFFFFFFFF

    return a, b, c, d


def hmac64(challenge: bytes, secret: bytes) -> bytes:
    """Compute Skynet/ONEMT 8-byte MAC from 8-byte challenge and 8-byte secret."""
    if len(challenge) != 8 or len(secret) != 8:
        raise ValueError("challenge and secret must each be 8 bytes")
    ch_lo, ch_hi = struct.unpack("<2I", challenge)
    sec_lo, sec_hi = struct.unpack("<2I", secret)
    pattern = struct.pack("<4I", ch_hi, ch_lo, sec_hi, sec_lo)
    a, b, c, d = _md5_compress_no_add(pattern * 4)
    return struct.pack("<2I", (c ^ d) & 0xFFFFFFFF, (b ^ a) & 0xFFFFFFFF)


def des_encode(plaintext: bytes, secret: bytes) -> bytes:
    """Encrypt bytes with DES-ECB and ISO 7816-4 padding (0x80 followed by 0x00s)."""
    if len(secret) < 8:
        raise ValueError("DES key must be at least 8 bytes")
    text_len = len(plaintext)
    # Skynet always pads to the next 8-byte block boundary using 0x80 then zeros.
    padded_len = (text_len + 8) & ~7
    padded = bytearray(padded_len)
    padded[:text_len] = plaintext
    padded[text_len] = 0x80
    cipher = DES.new(secret[:8], DES.MODE_ECB)
    return cipher.encrypt(bytes(padded))


def skynet_hashkey(data: bytes) -> bytes:
    """Compress variable-length bytes into an 8-byte digest (DJB2 + JS hash LE)."""
    djb_hash = 5381
    js_hash = 1315423911
    for byte in data:
        djb_hash = (djb_hash + (djb_hash << 5) + byte) & 0xFFFFFFFF
        js_hash = (js_hash ^ ((js_hash << 5) + byte + (js_hash >> 2))) & 0xFFFFFFFF
    return struct.pack("<2I", djb_hash, js_hash)


def xor_crypt(data: bytes, key: bytes) -> bytes:
    """Apply symmetric byte-wise XOR with a repeating key (onemtencrypt.xor)."""
    if not key:
        raise ValueError("XOR key cannot be empty")
    key_len = len(key)
    return bytes(byte ^ key[index % key_len] for index, byte in enumerate(data))
