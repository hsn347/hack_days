"""
تحليل libcocos2dlua.so لإيجاد DH prime المستخدم في ldhexchange
يستخدم capstone لـ ARM64 disassembly
"""
import struct, sys

def parse_elf64(data):
    """استخراج معلومات ELF64"""
    assert data[:4] == b'\x7fELF', "ليس ELF!"
    ei_class = data[4]  # 2 = 64-bit
    assert ei_class == 2, "ليس 64-bit!"
    
    # ELF header
    e_type, e_machine, e_version = struct.unpack_from('<HHI', data, 0x10)
    e_entry, e_phoff, e_shoff = struct.unpack_from('<QQQ', data, 0x18)
    e_flags, e_ehsize, e_phentsize, e_phnum = struct.unpack_from('<IHHH', data, 0x30)
    e_shentsize, e_shnum, e_shstrndx = struct.unpack_from('<HHH', data, 0x3A)
    
    # Section headers
    sections = []
    for i in range(e_shnum):
        off = e_shoff + i * e_shentsize
        sh = struct.unpack_from('<IIQQQQIIQQ', data, off)
        sections.append({
            'sh_name': sh[0], 'sh_type': sh[1], 'sh_flags': sh[2],
            'sh_addr': sh[3], 'sh_offset': sh[4], 'sh_size': sh[5],
            'sh_link': sh[6], 'sh_info': sh[7]
        })
    
    # String table for section names
    shstr = sections[e_shstrndx]
    shstr_data = data[shstr['sh_offset']:shstr['sh_offset']+shstr['sh_size']]
    
    def get_sec_name(idx):
        end = shstr_data.index(b'\x00', idx)
        return shstr_data[idx:end].decode()
    
    result = {}
    for s in sections:
        name = get_sec_name(s['sh_name'])
        result[name] = s
    
    # Dynamic symbol table
    dynsym = result.get('.dynsym')
    dynstr = result.get('.dynstr')
    
    symbols = {}
    if dynsym and dynstr:
        sym_data = data[dynsym['sh_offset']:dynsym['sh_offset']+dynsym['sh_size']]
        str_data = data[dynstr['sh_offset']:dynstr['sh_offset']+dynstr['sh_size']]
        
        sym_size = 24  # Elf64_Sym size
        for i in range(0, len(sym_data), sym_size):
            s = struct.unpack_from('<IBBHQQ', sym_data, i)
            name_idx = s[0]
            st_value = s[4]  # virtual address
            st_size = s[5]
            
            end = str_data.index(b'\x00', name_idx)
            name = str_data[name_idx:end].decode()
            if name:
                symbols[name] = {'addr': st_value, 'size': st_size}
    
    return result, symbols

def va_to_offset(va, sections):
    """تحويل virtual address إلى file offset"""
    for name, s in sections.items():
        if s['sh_addr'] <= va < s['sh_addr'] + s['sh_size']:
            return s['sh_offset'] + (va - s['sh_addr'])
    return None

def main():
    so_path = 'E:/osmanli/libcocos2dlua.so'
    print(f"Loading {so_path}...")
    data = open(so_path, 'rb').read()
    print(f"Size: {len(data):,} bytes")
    
    sections, symbols = parse_elf64(data)
    print(f"Sections: {len(sections)}, Symbols: {len(symbols)}")
    
    # ابحث عن luaopen_crypt
    crypt_sym = symbols.get('luaopen_crypt')
    if crypt_sym:
        print(f"\nluaopen_crypt: va=0x{crypt_sym['addr']:X}, size={crypt_sym['size']}")
        fn_offset = va_to_offset(crypt_sym['addr'], sections)
        if fn_offset:
            print(f"  File offset: 0x{fn_offset:X}")
            fn_code = data[fn_offset:fn_offset + min(crypt_sym['size'] or 512, 1024)]
            print(f"  First 64 bytes: {fn_code[:64].hex()}")
    else:
        print("luaopen_crypt not in dynsym")
        # ابحث بطريقة بديلة
        for sym_name in ['_luaopen_crypt', 'Java_luaopen_crypt']:
            if sym_name in symbols:
                print(f"  Found as: {sym_name}")
    
    # أبحث عن ldhexchange و ldhsecret - هي static functions لكن نحاول
    print("\nAll crypt-related exports:")
    for name, info in symbols.items():
        if any(kw in name.lower() for kw in ['crypt', 'hmac', 'dh', 'hash', 'md5', 'sha']):
            print(f"  {name}: va=0x{info['addr']:X}")
    
    # الآن ابحث عن الـ prime في قسم .rodata
    rodata = sections.get('.rodata')
    if rodata:
        print(f"\n.rodata: offset=0x{rodata['sh_offset']:X}, size=0x{rodata['sh_size']:X}")
        rod = data[rodata['sh_offset']:rodata['sh_offset']+rodata['sh_size']]
        
        # ابحث عن القيم الكبيرة
        found_primes = []
        for i in range(0, len(rod)-8, 8):
            val_le = struct.unpack('<Q', rod[i:i+8])[0]
            val_be = struct.unpack('>Q', rod[i:i+8])[0]
            
            for val, order in [(val_le, 'LE'), (val_be, 'BE')]:
                if val > 0x7F00000000000000 and val != 0xFFFFFFFFFFFFFFFF:
                    # قد يكون prime
                    found_primes.append((i, val, order, hex(val)))
        
        print(f"\nPotential prime constants in .rodata ({len(found_primes)} found):")
        for off, val, order, hx in found_primes[:20]:
            print(f"  .rodata+0x{off:X} [{order}]: {hx}")
    
    # البحث في كل الـ sections عن القيمة التي وجدناها سابقاً
    target_le = struct.pack('<Q', 0xFFFFFFFFFFFFFFC5)
    pos = data.find(target_le)
    if pos >= 0:
        ctx = data[pos-32:pos+64]
        print(f"\n0xFFFFFFFFFFFFFFC5 found at file offset 0x{pos:X}")
        print(f"Context: {ctx.hex()}")
        # أي section هذا؟
        for name, s in sections.items():
            if s['sh_offset'] <= pos < s['sh_offset'] + s['sh_size']:
                print(f"  In section: {name}")

if __name__ == '__main__':
    main()
