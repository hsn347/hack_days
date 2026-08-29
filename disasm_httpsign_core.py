import capstone

f = open('temp_libs/lib/arm64-v8a/libdaemonutil.so', 'rb')
data = f.read()

cs = capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_ARM)

print("=== Disassembling 0x950c0 to 0x95200 ===")
code = data[0x950c0:0x95200]
for insn in cs.disasm(code, 0x950c0):
    print(f'  {hex(insn.address)}: {insn.mnemonic:<8} {insn.op_str}')
