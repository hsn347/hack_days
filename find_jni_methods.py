import struct

with open('temp_libs/lib/arm64-v8a/libdaemonutil.so', 'rb') as f:
    data = f.read()

# Search for strings
for target in [b'encryptPacketForUC', b'decryptPacketForUC', b'getOriginAppKey', b'httpSign', b'signWithAppKey']:
    pos = data.find(target)
    print(f'String {target.decode()}: file offset={hex(pos)}')
    if pos != -1:
        # Search for 64-bit pointer to this string (little-endian)
        # Note: in PIE/ELF, pointer in .data.rel.ro will be pos (or pos + load_base)
        # Or referenced in assembly via ADRP + ADD
        ptr_le = struct.pack('<Q', pos)
        ptr_pos = 0
        found_ptrs = []
        while True:
            idx = data.find(ptr_le, ptr_pos)
            if idx == -1: break
            found_ptrs.append(hex(idx))
            ptr_pos = idx + 1
        print(f'  Pointers to string: {found_ptrs}')
