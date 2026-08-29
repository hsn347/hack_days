from elftools.elf.elffile import ELFFile

f = open('temp_libs/lib/arm64-v8a/libdaemonutil.so', 'rb')
elffile = ELFFile(f)
dynsym = elffile.get_section_by_name('.dynsym')
rela_plt = elffile.get_section_by_name('.rela.plt')
plt_section = elffile.get_section_by_name('.plt')
plt_vma = plt_section['sh_addr']

f.seek(0)
data = f.read()

# Check PLT 0x16c180
for i, rel in enumerate(rela_plt.iter_relocations()):
    plt_addr = plt_vma + 32 + i * 16
    if plt_addr in [0x16c180, 0x16bce0, 0x16bcf0, 0x16bd00, 0x16bd10, 0x16bd20, 0x16bd30, 0x16bd40, 0x16bd50, 0x16bd60]:
        sym = dynsym.get_symbol(rel['r_info_sym'])
        print(f'{hex(plt_addr)} -> {sym.name}')

# Check data at 0x6c8ec
print(f'Data at 0x6c8ec (len 64): {data[0x6c8ec:0x6c8ec+64]}')
