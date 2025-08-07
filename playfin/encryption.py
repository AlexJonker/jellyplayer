from base64 import b64encode, b64decode
import os

def xor_cipher(text, key):
    return "".join(chr(ord(c) ^ ord(key[i % len(key)])) for i, c in enumerate(text))

def encrypt_password(password, key):
    encrypted = xor_cipher(password, key)
    return b64encode(encrypted.encode()).decode()

def decrypt_password(encrypted_password, key):
    decoded = b64decode(encrypted_password.encode()).decode()
    return xor_cipher(decoded, key)

def generate_key():
    return b64encode(os.urandom(16)).decode()

