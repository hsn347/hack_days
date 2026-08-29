import base64

def decrypt(data_b64, key_b64):
    data = bytearray(base64.b64decode(data_b64))
    key = base64.b64decode(key_b64)
    length = len(data)
    length2 = len(key)
    i = 0
    i2 = 0
    while i < length:
        if i2 >= length2:
            i2 = 0
        data[i] = data[i] ^ key[i2]
        i += 1
        i2 += 1
    return data.decode('utf-8')

print('k1: ', decrypt("EwMTEQUAAAg=\n", "Y29yZQ==\n"), '=', decrypt("AgEWFwwGFg==\n", "Y29yZQ==\n"))
print('k2: ', decrypt("Ah8CDAc=\n", "Y29yZQ==\n"))
print('k3: ', decrypt("FwYfABAbEwgT\n", "Y29yZQ==\n"))
print('k4: ', decrypt("Ew4RDgIIFwsCAhc=\n", "Y29yZQ==\n"))
print('k5: ', decrypt("Dw4cAg==\n", "Y29yZQ==\n"))
print('k6: ', decrypt("EAsbAQ==\n", "Y29yZQ==\n"))
print('k7: ', decrypt("AAcTCw0KHg==\n", "Y29yZQ==\n"))
print('k8: ', decrypt("ERwGBBcaAQ==\n", "Y29yZQ==\n"), 'Ug=', decrypt("Ug==\n", "Y29yZQ==\n"), 'Uw=', decrypt("Uw==\n", "Y29yZQ==\n"))
print('k9: ', decrypt("EQoDAQIbEw==\n", "Y29yZQ==\n"))
print('k10:', decrypt("EAoREBEKHwoHCg==\n", "Y29yZQ==\n"), '=', decrypt("LitH\n", "Y29yZQ==\n"))
print('k11:', decrypt("EAYVCw==\n", "Y29yZQ==\n"))
