"""

This Python script is a crucial utility for enabling secure communication within the WLEDVideoSync application,
particularly for the mobile camera streaming feature. Its sole purpose is to generate a self-signed SSL/TLS certificate
and a corresponding private key.

In short, this file makes it possible for your phone's browser to securely connect to the WLEDVideoSync server and
stream video from its camera. Without it, the mobile streaming feature would not work on most modern devices.

"""

import os
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from datetime import datetime, timedelta, timezone

def generate_self_signed_cert(cert_file='cert.pem', key_file='key.pem', hostname='127.0.0.1'):
    """Generates a self-signed SSL/TLS certificate and private key for secure communication.

    This function creates a new certificate and key if they do not already exist, enabling secure connections for
    features like mobile camera streaming.
    It returns the paths to the certificate and key files, or existing ones if already present.

    Args:
        cert_file (str, optional): Path to the certificate file. Defaults to 'cert.pem'.
        key_file (str, optional): Path to the private key file. Defaults to 'key.pem'.
        hostname (str, optional): Hostname to use in the certificate. Defaults to '127.0.0.1'.

    Returns:
        tuple: A tuple containing the certificate file path and key file path.
    """
    if os.path.exists(cert_file) and os.path.exists(key_file):
        print('using existing certificate...')
        return cert_file, key_file

    print('Generating self-signed certificate...')

    try:

        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, hostname),
        ])
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.now(timezone.utc) - timedelta(minutes=1))
            .not_valid_after(datetime.now(timezone.utc) + timedelta(days=365))
            .add_extension(
                x509.SubjectAlternativeName([x509.DNSName(hostname)]),
                critical=False,
            )
            .sign(key, hashes.SHA256())
        )

        # Write cert and key to files
        with open(cert_file, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))
        with open(key_file, "wb") as f:
            f.write(key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.TraditionalOpenSSL,
                serialization.NoEncryption()
            ))

        print('Certificate created.')

    except Exception as e:
        print(f'Error to generate certificate:{e}')
        cert_file = None
        key_file = None

    return cert_file, key_file

if __name__ == "__main__":
    generate_self_signed_cert()