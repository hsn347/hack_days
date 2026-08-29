import struct, capstone

f = open('temp_libs/lib/arm64-v8a/libdaemonutil.so', 'rb')
data = f.read()

cs = capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_ARM)

print("=== Disassembling init (0x94ad4) ===")
code = data[0x94ad4:0x94ad4+500]
for insn in cs.disasm(code, 0x94ad4):
    print(f'  {hex(insn.address)}: {insn.mnemonic:<8} {insn.op_str}')
