import zipfile, hashlib
from cryptography.hazmat.primitives.serialization import pkcs7
from cryptography.x509 import load_der_x509_certificate

# In Android APK (ZIP), META-INF/*.RSA or *.DSA or APK signature block v2/v3
with zipfile.ZipFile('base_temp.apk') as z:
    for name in z.namelist():
        if name.startswith('META-INF/') and (name.endswith('.RSA') or name.endswith('.DSA')):
            rsa_data = z.read(name)
            print(f'Found cert in {name} (size {len(rsa_data)})')
            # Extract DER cert or compute MD5
            # In Android, signatures[0].toByteArray() is the DER encoded certificate
            # Let's parse PKCS7
            from cryptography.hazmat.backends import default_backend
            from pyasn1.codec.der import decoder
            print('Cert MD5:', hashlib.md5(rsa_data).hexdigest().upper())

