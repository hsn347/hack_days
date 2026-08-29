import zipfile, hashlib
from cryptography.hazmat.primitives.serialization.pkcs7 import load_der_pkcs7_certificates
from cryptography.hazmat.primitives import serialization

with zipfile.ZipFile('base_temp.apk') as z:
    for name in z.namelist():
        if name.startswith('META-INF/') and (name.endswith('.RSA') or name.endswith('.DSA')):
            data = z.read(name)
            certs = load_der_pkcs7_certificates(data)
            for cert in certs:
                der_bytes = cert.public_bytes(serialization.Encoding.DER) if hasattr(cert, 'public_bytes') else None
                # Compute MD5
                from cryptography.hazmat.primitives import serialization
                der_bytes = cert.public_bytes(serialization.Encoding.DER)
                md5_hex = hashlib.md5(der_bytes).hexdigest().upper()
                md5_colon = ":".join(md5_hex[i:i+2] for i in range(0, len(md5_hex), 2))
                print('Certificate MD5 (colon):', md5_colon)
                print('Certificate MD5 (raw):  ', md5_hex)
