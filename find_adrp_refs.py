import capstone
from elftools.elf.elffile import ELFFile

f = open('temp_libs/lib/arm64-v8a/libdaemonutil.so', 'rb')
data = f.read()
f.seek(0)
elffile = ELFFile(f)

# Find .text section
for s in elffile.iter_sections():
    if s.name == '.text':
        text_vma = s['sh_addr']
        text_off = s['sh_offset']
        text_sz = s['sh_size']
        print(f'.text: vma={hex(text_vma)}, offset={hex(text_off)}, size={hex(text_sz)}')
        break

cs = capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_ARM)
cs.detail = True

# Disassemble .text and track ADRP + ADD / LDR
text_code = data[text_off:text_off+text_sz]
adrp_regs = {}

# String addresses in VMA
targets = {
    0x6da98: 'encryptPacketForUC',
    0x6cffe: 'decryptPacketForUC',
    0x6cca6: 'getOriginAppKey',
    0x6d43e: 'httpSign',
    0x6dd6b: 'signWithAppKey'
}

for insn in cs.disasm(text_code, text_vma):
    if insn.mnemonic == 'adrp':
        reg = insn.op_str.split(',')[0].strip()
        val = int(insn.op_str.split('#')[-1], 16)
        adrp_regs[reg] = val
    elif insn.mnemonic in ('add', 'ldr') and '#' in insn.op_str:
        parts = insn.op_str.split(',')
        dst_reg = parts[0].strip()
        src_reg = parts[1].strip()
        imm_str = insn.op_str.split('#')[-1].rstrip(']')
        try:
            imm = int(imm_str, 16) if imm_str.startswith('0x') else int(imm_str)
            if src_reg in adrp_regs:
                full_addr = adrp_regs[src_reg] + imm
                if full_addr in targets:
                    print(f'Reference to {targets[full_addr]} at {hex(insn.address)} (ADRP+ADD)!')
                    # Print 40 instructions around this location
                    idx_in_text = insn.address - text_vma
                    snippet = text_code[max(0, idx_in_text-60):idx_in_text+120]
                    start_addr = max(text_vma, insn.address-60)
                    for sub_insn in cs.disasm(snippet, start_addr):
                        print(f'   {hex(sub_insn.address)}: {sub_insn.mnemonic:<8} {sub_insn.op_str}')
                    print('='*60)
        except:
            pass
