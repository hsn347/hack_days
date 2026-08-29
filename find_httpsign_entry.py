import struct, capstone

f = open('temp_libs/lib/arm64-v8a/libdaemonutil.so', 'rb')
data = f.read()

cs = capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_ARM)

# In parse_rela_entries, httpSign was after 0x371c0
# Let's inspect 0x371c0 to 0x37220
for i in range(10):
    pos = 0x371a0 + i * 24
    r_offset, r_info, r_addend = struct.unpack('<QQq', data[pos:pos+24])
    print(f'Rela [{i}]: r_offset={hex(r_offset)} -> r_addend={hex(r_addend)}')
    if 0x922a0 <= r_addend < 0x922a0 + 0xd98e0:
        print(f'  >>> Code at {hex(r_addend)}:')
        code = data[r_addend:r_addend+120]
        for insn in cs.disasm(code, r_addend):
            print(f'      {hex(insn.address)}: {insn.mnemonic:<8} {insn.op_str}')
