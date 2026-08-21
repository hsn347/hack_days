"""
Disassemble powmod function to find DH prime
"""
import struct, capstone

data = open('E:/osmanli/libcocos2dlua.so', 'rb').read()

def parse_sections(data):
    e_shoff, = struct.unpack_from('<Q', data, 0x28)
    e_shentsize, e_shnum, e_shstrndx = struct.unpack_from('<HHH', data, 0x3A)
    sections = []
    for i in range(e_shnum):
        off = e_shoff + i * e_shentsize
        sh = struct.unpack_from('<IIQQQQIIQQ', data, off)
        sections.append({'sh_name':sh[0],'sh_addr':sh[3],'sh_offset':sh[4],'sh_size':sh[5]})
    shstr = sections[e_shstrndx]
    shstr_d = data[shstr['sh_offset']:shstr['sh_offset']+shstr['sh_size']]
    result = {}
    for s in sections:
        idx = s['sh_name']
        end = shstr_d.index(b'\x00', idx)
        name = shstr_d[idx:end].decode()
        result[name] = s
    return result

def va2off(va, secs):
    for s in secs.values():
        if s['sh_addr'] <= va < s['sh_addr'] + s['sh_size']:
            return s['sh_offset'] + (va - s['sh_addr'])
    return None

secs = parse_sections(data)

md = capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_ARM)
md.detail = True

# disassemble the powmod function at 0x7483A0
powmod_va = 0x7483A0
powmod_off = va2off(powmod_va, secs)
print(f'powmod: VA=0x{powmod_va:X}, file_offset=0x{powmod_off:X}')

fn_bytes = data[powmod_off:powmod_off + 600]
print('\n=== powmod / dhexchange_internal ===')
for insn in md.disasm(fn_bytes, powmod_va):
    # بحث عن MOVZ/MOVK (تحميل constants)
    extra = ""
    if insn.mnemonic in ('movz', 'movk'):
        extra = " <<< CONST"
    elif insn.mnemonic == 'ldr' and '#0x' in insn.op_str:
        extra = " <<< LDR const"
    
    print(f'  0x{insn.address:X}: {insn.mnemonic:8} {insn.op_str}{extra}')
    
    if insn.mnemonic == 'ret':
        break
    if insn.address - powmod_va > 500:
        print('  ...(truncated)')
        break

# أيضاً disassemble ldhsecret للمقارنة
print('\n=== Looking for ldhsecret ===')
# ابحث عن "dhsecret" string
ds_off = data.find(b'dhsecret\x00')
ds_va = None
for s in secs.values():
    if s['sh_offset'] <= ds_off < s['sh_offset'] + s['sh_size']:
        ds_va = s['sh_addr'] + (ds_off - s['sh_offset'])
        break
print(f'"dhsecret" string VA: 0x{ds_va:X}')

# ابحث عن pointer له
for off in range(0, len(data)-8, 8):
    ptr = struct.unpack_from('<Q', data, off)[0]
    if ptr == ds_va:
        next_ptr = struct.unpack_from('<Q', data, off+8)[0]
        print(f'  Table entry at 0x{off:X}: name=0x{ptr:X}, fn=0x{next_ptr:X}')
        fn_off = va2off(next_ptr, secs)
        if fn_off:
            print(f'  ldhsecret file_offset: 0x{fn_off:X}')
            fn_bytes2 = data[fn_off:fn_off+300]
            print('  === ldhsecret disassembly ===')
            for insn in md.disasm(fn_bytes2, next_ptr):
                extra = " <<< CONST" if insn.mnemonic in ('movz','movk') else ""
                print(f'    0x{insn.address:X}: {insn.mnemonic:8} {insn.op_str}{extra}')
                if insn.mnemonic == 'ret': break
                if insn.address - next_ptr > 200: break
