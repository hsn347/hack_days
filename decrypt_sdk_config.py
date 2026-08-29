import zipfile, base64
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

key = b"MGk01bO6PyIiA6Dc"
iv = b"s6tsKLr6kbnTC1bK"

# Search in resources.arsc for onemt_config_text
import extract_words # we have ARSC parser

with zipfile.ZipFile('base_temp.apk') as z:
    arsc = z.read('resources.arsc')

# Extract string onemt_config_text from ARSC
import struct

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

tab_type, tab_hdr_sz, tab_sz = struct.unpack('<HHI', arsc[:8])
global_strings, pkg_offset = parse_string_pool(arsc, tab_hdr_sz)
type_strings_offset = pkg_offset + struct.unpack('<I', arsc[pkg_offset+268:pkg_offset+272])[0]
key_strings_offset = pkg_offset + struct.unpack('<I', arsc[pkg_offset+276:pkg_offset+280])[0]
type_strings, _ = parse_string_pool(arsc, type_strings_offset)
key_strings, cur_offset = parse_string_pool(arsc, key_strings_offset)

config_b64 = None
for i, k in enumerate(key_strings):
    if k == 'onemt_config_text':
        print(f'Found key onemt_config_text at {i}')
        # Find entry
        while cur_offset < len(arsc):
            ctype, c_hdr_sz, c_sz = struct.unpack('<HHI', arsc[cur_offset:cur_offset+8])
            if c_sz == 0: break
            if ctype == 0x0201:
                entry_count = struct.unpack('<I', arsc[cur_offset+12:cur_offset+16])[0]
                entries_start = struct.unpack('<I', arsc[cur_offset+16:cur_offset+20])[0]
                for j in range(entry_count):
                    entry_off = struct.unpack('<I', arsc[cur_offset+c_hdr_sz+j*4:cur_offset+c_hdr_sz+j*4+4])[0]
                    if entry_off != 0xFFFFFFFF:
                        pos = cur_offset + entries_start + entry_off
                        e_sz, e_flags, e_key = struct.unpack('<HHI', arsc[pos:pos+8])
                        if e_key == i:
                            val_data = struct.unpack('<I', arsc[pos+12:pos+16])[0]
                            config_b64 = global_strings[val_data]
                            break
            if config_b64: break
            cur_offset += c_sz
        break

if config_b64:
    print('Found onemt_config_text Base64 (len %d)' % len(config_b64))
    raw_enc = base64.b64decode(config_b64)
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend()).decryptor()
    plain = cipher.update(raw_enc) + cipher.finalize()
    # Unpad PKCS7
    pad_len = plain[-1]
    plain = plain[:-pad_len]
    print('DECRYPTED SDK CONFIG:')
    print(plain.decode('utf-8'))
