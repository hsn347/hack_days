import struct
import capstone

with open('temp_libs/lib/arm64-v8a/libdaemonutil.so', 'rb') as f:
    data = f.read()

cs = capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_ARM)

# JNINativeMethods table entries at 0x37058
for i in range(10):
    entry_pos = 0x37058 + i * 24
    if entry_pos + 24 > len(data): break
    name_ptr, sig_ptr, fn_ptr = struct.unpack('<QQQ', data[entry_pos:entry_pos+24])
    if name_ptr < len(data) and sig_ptr < len(data):
        name = data[name_ptr:].split(b'\x00')[0].decode('utf-8', 'ignore')
        sig = data[sig_ptr:].split(b'\x00')[0].decode('utf-8', 'ignore')
        print(f'\n=== JNI Method [{i}]: {name} {sig} -> fnPtr: {hex(fn_ptr)} ===')
        
        # Disassemble first 30 instructions of fn_ptr
        if fn_ptr < len(data):
            code = data[fn_ptr:fn_ptr+120]
            for insn in cs.disasm(code, fn_ptr):
                print(f'  {hex(insn.address)}: {insn.mnemonic}\t{insn.op_str}')
