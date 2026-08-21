"""
Disassemble luaopen_crypt and ldhexchange from libcocos2dlua.so
to find the DH prime constant
"""
import struct, capstone

data = open('E:/osmanli/libcocos2dlua.so', 'rb').read()

def parse_elf(data):
    e_shoff, = struct.unpack_from('<Q', data, 0x28)
    e_shentsize, e_shnum, e_shstrndx = struct.unpack_from('<HHH', data, 0x3A)
    sections = []
    for i in range(e_shnum):
        off = e_shoff + i * e_shentsize
        sh = struct.unpack_from('<IIQQQQIIQQ', data, off)
        sections.append({'name':'','sh_name':sh[0],'sh_addr':sh[3],'sh_offset':sh[4],'sh_size':sh[5]})
    shstr = sections[e_shstrndx]
    shstr_data = data[shstr['sh_offset']:shstr['sh_offset']+shstr['sh_size']]
    sec_dict = {}
    for s in sections:
        idx = s['sh_name']
        end = shstr_data.index(b'\x00', idx)
        name = shstr_data[idx:end].decode()
        s['name'] = name
        sec_dict[name] = s
    dynsym = sec_dict.get('.dynsym')
    dynstr = sec_dict.get('.dynstr')
    syms = {}
    if dynsym and dynstr:
        sd = data[dynsym['sh_offset']:dynsym['sh_offset']+dynsym['sh_size']]
        nd = data[dynstr['sh_offset']:dynstr['sh_offset']+dynstr['sh_size']]
        for i in range(0, len(sd), 24):
            ni, _, _, _, va, sz = struct.unpack_from('<IBBHQQ', sd, i)
            if va:
                end = nd.index(b'\x00', ni)
                name = nd[ni:end].decode()
                syms[name] = {'va': va, 'size': sz}
    return sec_dict, syms

def va2off(va, sections):
    for s in sections.values():
        if s['sh_addr'] <= va < s['sh_addr'] + s['sh_size']:
            return s['sh_offset'] + (va - s['sh_addr'])
    return None

def off2va(off, sections):
    for s in sections.values():
        if s['sh_offset'] <= off < s['sh_offset'] + s['sh_size']:
            return s['sh_addr'] + (off - s['sh_offset'])
    return None

secs, syms = parse_elf(data)

lc_info = syms.get('luaopen_crypt', {})
lc_va = lc_info.get('va', 0)
lc_size = lc_info.get('size', 512)
print(f'luaopen_crypt: VA=0x{lc_va:X}, size={lc_size}')

lc_off = va2off(lc_va, secs)
print(f'  File offset: 0x{lc_off:X}')

md = capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_ARM)
md.detail = True

fn_bytes = data[lc_off:lc_off + max(lc_size, 512)]
print('\n=== luaopen_crypt disassembly ===')

adrp_bases = {}
branch_targets = []

for insn in md.disasm(fn_bytes, lc_va):
    print(f'  0x{insn.address:X}: {insn.mnemonic:8} {insn.op_str}')
    
    # تتبع ADRP + ADD/LDR لإيجاد عناوين البيانات
    if insn.mnemonic == 'adrp':
        reg = insn.operands[0].reg
        page = insn.operands[1].imm
        adrp_bases[reg] = page
    elif insn.mnemonic in ('add', 'ldr') and len(insn.operands) >= 2:
        try:
            if hasattr(insn.operands[1], 'reg') and insn.operands[1].reg in adrp_bases:
                base = adrp_bases[insn.operands[1].reg]
                if len(insn.operands) > 2 and hasattr(insn.operands[2], 'imm'):
                    addr = base + insn.operands[2].imm
                    print(f'    >>> DATA REF: 0x{addr:X}')
        except: pass
    elif insn.mnemonic == 'bl':
        try:
            target = insn.operands[0].imm
            branch_targets.append(target)
            print(f'    >>> CALL: 0x{target:X}')
        except: pass
    
    if insn.mnemonic == 'ret':
        break
    if insn.address - lc_va > 1000:
        break

# الآن نبحث عن "dhexchange" string في الـ data وننظر ماذا يشير إليه
print('\n=== Searching for dhexchange string reference ===')
dhex_str_off = data.find(b'dhexchange\x00')
print(f'"dhexchange" string at file offset: 0x{dhex_str_off:X}')
dhex_str_va = off2va(dhex_str_off, secs)
print(f'"dhexchange" VA: 0x{dhex_str_va:X}')

# ابحث عن مؤشر يشير لهذا العنوان في .rodata
for off in range(0, len(data)-8, 8):
    ptr = struct.unpack_from('<Q', data, off)[0]
    if ptr == dhex_str_va and 0x100000 < ptr < 0x2000000:
        print(f'  Pointer at file offset 0x{off:X} -> 0x{ptr:X}')
        # العنصر السابق في الـ table هو اسم السابق، العنصر التالي هو function pointer
        next_ptr = struct.unpack_from('<Q', data, off+8)[0]
        prev_ptr = struct.unpack_from('<Q', data, off-8)[0]
        print(f'    prev_ptr (prev func?): 0x{prev_ptr:X}')
        print(f'    next_ptr (func ptr?):  0x{next_ptr:X}')
        if 0x100000 < next_ptr < 0x2000000:
            # قد يكون function pointer
            fn_off = va2off(next_ptr, secs)
            if fn_off:
                print(f'    Function offset: 0x{fn_off:X}')
                print(f'\n=== ldhexchange disassembly (candidate) ===')
                fn_bytes2 = data[fn_off:fn_off+300]
                for insn2 in md.disasm(fn_bytes2, next_ptr):
                    print(f'  0x{insn2.address:X}: {insn2.mnemonic:8} {insn2.op_str}')
                    if insn2.mnemonic == 'ret':
                        break
