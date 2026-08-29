from elftools.elf.elffile import ELFFile

f = open('temp_libs/lib/arm64-v8a/libdaemonutil.so', 'rb')
elffile = ELFFile(f)

dynsym = elffile.get_section_by_name('.dynsym')
rela_plt = elffile.get_section_by_name('.rela.plt')
plt_section = elffile.get_section_by_name('.plt')
plt_vma = plt_section['sh_addr']
sz = plt_section['sh_size']

print('.plt at %s, size=%s' % (hex(plt_vma), hex(sz)))

if rela_plt and dynsym:
    for i, rel in enumerate(rela_plt.iter_relocations()):
        sym_idx = rel['r_info_sym']
        sym = dynsym.get_symbol(sym_idx)
        plt_addr = plt_vma + 32 + i * 16
        got_off = rel['r_offset']
        # Print relevant symbols
        if any(k in sym.name.lower() for k in ['aes', 'des', 'encrypt', 'decrypt', 'md5', 'sha', 'base64', 'string', 'crypt']):
            print('PLT [%s]: %s' % (hex(plt_addr), sym.name))
