import zipfile, struct

with zipfile.ZipFile('base_temp.apk') as z:
    arsc = z.read('resources.arsc')

tab_type, tab_hdr_sz, tab_sz = struct.unpack('<HHI', arsc[:8])

def parse_string_pool(data, offset):
    ctype, c_hdr_sz, c_sz = struct.unpack('<HHI', data[offset:offset+8])
    scount, stcount, flags, sstart, ststart = struct.unpack('<IIIII', data[offset+8:offset+28])
    is_utf8 = bool(flags & (1 << 8))
    offsets = [struct.unpack('<I', data[offset+28+i*4:offset+32+i*4])[0] for i in range(scount)]
    pool_data_start = offset + sstart
    strings = []
    for off in offsets:
        pos = pool_data_start + off
        try:
            if is_utf8:
                u16len = data[pos]
                pos += 1
                if u16len & 0x80: pos += 1
                u8len = data[pos]
                pos += 1
                if u8len & 0x80:
                    u8len = ((u8len & 0x7f) << 8) | data[pos]
                    pos += 1
                s = data[pos:pos+u8len].decode('utf-8', errors='replace')
            else:
                u16len = struct.unpack('<H', data[pos:pos+2])[0]
                pos += 2
                s = data[pos:pos+u16len*2].decode('utf-16le', errors='replace')
            strings.append(s)
        except:
            strings.append('')
    return strings, offset + c_sz

global_strings, pkg_offset = parse_string_pool(arsc, tab_hdr_sz)
type_strings_offset = pkg_offset + struct.unpack('<I', arsc[pkg_offset+268:pkg_offset+272])[0]
key_strings_offset = pkg_offset + struct.unpack('<I', arsc[pkg_offset+276:pkg_offset+280])[0]
type_strings, _ = parse_string_pool(arsc, type_strings_offset)
key_strings, cur_offset = parse_string_pool(arsc, key_strings_offset)

results = {}
while cur_offset < len(arsc):
    if cur_offset + 8 > len(arsc): break
    ctype, c_hdr_sz, c_sz = struct.unpack('<HHI', arsc[cur_offset:cur_offset+8])
    if c_sz == 0: break
    if ctype == 0x0201: # RES_TABLE_TYPE_TYPE
        entry_count = struct.unpack('<I', arsc[cur_offset+12:cur_offset+16])[0]
        entries_start = struct.unpack('<I', arsc[cur_offset+16:cur_offset+20])[0]
        for i in range(entry_count):
            entry_off = struct.unpack('<I', arsc[cur_offset+c_hdr_sz+i*4:cur_offset+c_hdr_sz+i*4+4])[0]
            if entry_off != 0xFFFFFFFF:
                pos = cur_offset + entries_start + entry_off
                e_sz, e_flags, e_key = struct.unpack('<HHI', arsc[pos:pos+8])
                if e_key in [4201, 4202]:
                    val_sz = struct.unpack('<H', arsc[pos+8:pos+10])[0]
                    val_type = arsc[pos+11]
                    val_data = struct.unpack('<I', arsc[pos+12:pos+16])[0]
                    key_name = key_strings[e_key]
                    str_val = global_strings[val_data] if val_data < len(global_strings) else 'N/A'
                    results[key_name] = str_val
                    print(f'>>> {key_name} = "{str_val}"')
    cur_offset += c_sz

print('Final results:', results)
