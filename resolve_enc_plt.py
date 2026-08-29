from elftools.elf.elffile import ELFFile

f = open('temp_libs/lib/arm64-v8a/libdaemonutil.so', 'rb')
elffile = ELFFile(f)
dynsym = elffile.get_section_by_name('.dynsym')
rela_plt = elffile.get_section_by_name('.rela.plt')
plt_section = elffile.get_section_by_name('.plt')
plt_vma = plt_section['sh_addr']

for i, rel in enumerate(rela_plt.iter_relocations()):
    plt_addr = plt_vma + 32 + i * 16
    if plt_addr in [0x16bfe0, 0x16bff0, 0x16bf20]:
        sym = dynsym.get_symbol(rel['r_info_sym'])
        print(f'{hex(plt_addr)} -> {sym.name}')
