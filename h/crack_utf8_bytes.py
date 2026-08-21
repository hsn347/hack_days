import hashlib, hmac as hmac_lib

# Parse codepoints and reconstruct original UTF-8 bytes
CODEPOINT_HEX = "003afffd007bfffdfffdfffd004900300007fffdfffdfffdfffd005500280013fffd0046007c006bfffd0058fffd00440017fffd002500400047001900060032fffdfffd00090001000b002c0017007e0076fffd007cfffd001bfffdfffdfffdfffd005a0003006206a3fffdfffdfffdfffdfffd0034002a0064fffd003efffdfffdfffdfffdfffdfffdfffdfffdfffdfffd0044fffd006f002d007dfffd005b007cfffdfffdfffdc4bcdcbc0214000dfffdfffd002b005ffffdfffd00120014fffd0060fffd006c004efffd00160027fffd002cfffdfffdfffd0052fffd004efffdfffd005f00750058fffd000efffd003a0724fffd0015fffd0057fffdfffdfffd004afffd0006fffdfffd000e002b001e00260044000bfffd0001006a0024fffdfffdfffd006cfffd0011fffd001d0057fffdfffd002e000cfffdfffd0056fffd0007fffd006c004c003c0075fffd00790074fffd00750063004402980041001c0045000efffdfffd001bfffd00540002fffdfffdfffd0070006b005c0072fffd01760050001cfffd004c0011fffd00610055fffd0048fffdfffd0039fffd000efffd0012fffdfffdfffd00170044fffd0022fffdfffdfffdfffdfffdfffdfffd004000310073005c"

# Split into 4-char groups (each is a 16-bit codepoint)
cps = [int(CODEPOINT_HEX[i:i+4], 16) for i in range(0, len(CODEPOINT_HEX), 4)]
print(f"Codepoints: {len(cps)}")

# Reconstruct original UTF-8 bytes
# Each codepoint in the string came from UTF-8 decoding of the original bytes
# To get original bytes: encode each codepoint back to UTF-8
# FFFD = unknown original bytes (invalid UTF-8)
known_bytes = b''
unknown_positions = []
for i, cp in enumerate(cps):
    if cp == 0xFFFD:
        # Unknown - mark position, assume 1 byte (0x80-0xFF)
        unknown_positions.append(len(known_bytes))
        known_bytes += b'\x00'  # placeholder
    else:
        # Reconstruct UTF-8 encoding of this codepoint
        ch = chr(cp)
        utf8 = ch.encode('utf-8')
        known_bytes += utf8

print(f"Reconstructed bytes length (with placeholders): {len(known_bytes)}")
print(f"Unknown positions: {len(unknown_positions)}")
print(f"Reconstructed (known) hex: {known_bytes.hex()}")

# Non-FFFD codepoints = real sequences
non_fffd = [(i, cp) for i, cp in enumerate(cps) if cp != 0xFFFD]
print(f"\nNon-FFFD codepoints: {len(non_fffd)}")
for i, cp in non_fffd:
    print(f"  [{i}] U+{cp:04X} = {chr(cp) if cp < 0x80 else '?'}")

# Test if the known bytes (with 0x00 placeholders) can help us find the key
TESTS = [
    ('', '292acee0423c18171018f4cee8435606'),
    ('a', 'e8fe77a5f1a269da23330f658ef55889'),
    ('{}', 'd01ac4e2ad28d6503a38ec9f779bf424'),
    ('{"a":"1"}', '171980e57ef983a1b1df64bf9ec1163b'),
    ('hello world', '33a3b048e9a0351d341935ad4e133a32'),
]

def test(fn, name):
    r = [fn(t[0]) == t[1] for t in TESTS]
    n = sum(r)
    if n >= 2: print(f'  ({n}/5): {name}')
    return n == 5

print("\n=== Attempting key recovery with brute-force on unknown bytes ===")
# The key is likely a 16-byte chunk from the decrypted daemon
# Strategy: find 16-byte windows where placeholders = 0x00
# and test as HMAC key

def hmac_md5(k, d):
    return hmac_lib.new(k, d.encode(), hashlib.md5).hexdigest()

# Find windows with fewest unknowns
window_size = 16
for start in range(0, len(known_bytes) - window_size + 1, 1):
    window = known_bytes[start:start+window_size]
    # Count unknowns (0x00 placeholders at unknown positions)
    num_unknowns = sum(1 for pos in unknown_positions if start <= pos < start+window_size)
    if num_unknowns == 0:
        # All bytes known! Test directly
        if test(lambda j, k=window: hmac_md5(k, j), f'HMAC(bytes[{start}:{start+16}])'):
            print(f'KEY FOUND: {window.hex()}')
        if test(lambda j, k=window: hashlib.md5(j.encode()+k).hexdigest(), f'md5(j+bytes[{start}:{start+16}])'):
            print(f'KEY FOUND: {window.hex()}')
