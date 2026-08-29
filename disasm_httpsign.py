from elftools.elf.elffile import ELFFile
import capstone

f = open('temp_libs/lib/arm64-v8a/libdaemonutil.so', 'rb')
elffile = ELFFile(f)
dynsym = elffile.get_section_by_name('.dynsym')

cs = capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_ARM)

f.seek(0)
data = f.read()

for sym in dynsym.iter_symbols():
    if 'httpSign' in sym.name:
        addr = sym['st_value']
        sz = sym['st_size']
        print(f'\n=== Symbol {sym.name} at {hex(addr)} (size={sz}) ===')
        code = data[addr:addr+min(sz, 400)]
        for insn in cs.disasm(code, addr):
            print(f'  {hex(insn.address)}: {insn.mnemonic:<8} {insn.op_str}')
