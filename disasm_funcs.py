import struct, capstone

f = open('temp_libs/lib/arm64-v8a/libdaemonutil.so', 'rb')
data = f.read()

cs = capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_ARM)

funcs = [
    ('getOriginAppKey', 0x94ea8),
    ('encryptPacketForUC', 0x94cd8),
    ('decryptPacketForUC', 0x94dc0),
    ('init', 0x94ad4),
]

for name, addr in funcs:
    print(f'\n======================================================')
    print(f'FUNCTION: {name} at {hex(addr)}')
    print(f'======================================================')
    code = data[addr:addr+240]
    for insn in cs.disasm(code, addr):
        print(f'  {hex(insn.address)}: {insn.mnemonic:<8} {insn.op_str}')
