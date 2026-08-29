import struct, capstone
from elftools.elf.elffile import ELFFile
from elftools.elf.relocation import RelocationSection

f = open('temp_libs/lib/arm64-v8a/libdaemonutil.so', 'rb')
data = bytearray(f.read())
f.seek(0)
elffile = ELFFile(f)

def vma_to_offset(vma):
    for seg in elffile.iter_segments():
        if seg['p_type'] == 'PT_LOAD':
            if seg['p_vaddr'] <= vma < seg['p_vaddr'] + seg['p_filesz']:
                return vma - seg['p_vaddr'] + seg['p_offset']
    return None

for section in elffile.iter_sections():
    if isinstance(section, RelocationSection):
        for rel in section.iter_relocations():
            r_offset = rel['r_offset']
            r_type = rel['r_info_type']
            r_addend = rel['r_addend']
            if r_type == 1027: # R_AARCH64_RELATIVE
                file_off = vma_to_offset(r_offset)
                if file_off is not None and file_off + 8 <= len(data):
                    struct.pack_into('<Q', data, file_off, r_addend)

cs = capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_ARM)

methods = [
    ('encryptPacketForUC', 0x37058),
    ('init', 0x370a0),
    ('decryptPacketForUC', 0x370e8),
    ('getOriginAppKey', 0x37130),
    ('signWithAppKey', 0x37178),
    ('httpSign', 0x371c0)
]

for name, vma_off in methods:
    off = vma_to_offset(vma_off)
    name_vma, sig_vma, fn_vma = struct.unpack('<QQQ', data[off:off+24])
    
    name_off = vma_to_offset(name_vma)
    sig_off = vma_to_offset(sig_vma)
    fn_off = vma_to_offset(fn_vma)
    
    name_str = data[name_off:].split(b'\x00')[0].decode('utf-8', 'ignore') if name_off else '?'
    sig_str = data[sig_off:].split(b'\x00')[0].decode('utf-8', 'ignore') if sig_off else '?'
    print(f'\n======================================================')
    print(f'METHOD: {name_str} {sig_str} at fn_vma: {hex(fn_vma)} (file_off: {hex(fn_off) if fn_off else "?"})')
    print(f'======================================================')
    if fn_off is not None and fn_off < len(data):
        code = bytes(data[fn_off:fn_off+160])
        for insn in cs.disasm(code, fn_vma):
            print(f'  {hex(insn.address)}: {insn.mnemonic:<8} {insn.op_str}')
