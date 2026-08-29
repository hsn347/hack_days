import struct, capstone

f = open('temp_libs/lib/arm64-v8a/libdaemonutil.so', 'rb')
data = f.read()

cs = capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_ARM)

# In .rela.dyn (starts at 0x36f40), each entry is 24 bytes: (r_offset: uint64, r_info: uint64, r_addend: int64)
# Let's inspect entries around 0x37058
for i in range(15):
    pos = 0x37040 + i * 24
    r_offset, r_info, r_addend = struct.unpack('<QQq', data[pos:pos+24])
    r_type = r_info & 0xFFFFFFFF
    
    # What string is at r_addend?
    str_val = ''
    if 0 <= r_addend < len(data):
        str_val = data[r_addend:r_addend+40].split(b'\x00')[0].decode('utf-8', 'ignore')
        
    print(f'Rela [{i}]: r_offset={hex(r_offset)} -> r_addend={hex(r_addend)} (type={r_type}) string="{str_val}"')
    
    # If this is code (in .text), disassemble it!
    if 0x922a0 <= r_addend < 0x922a0 + 0xd98e0:
        print(f'  >>> Code at {hex(r_addend)}:')
        code = data[r_addend:r_addend+80]
        for insn in cs.disasm(code, r_addend):
            print(f'      {hex(insn.address)}: {insn.mnemonic:<8} {insn.op_str}')
