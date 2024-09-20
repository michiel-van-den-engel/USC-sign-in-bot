"""Hold the encrytor class in this module"""
import hashlib
import os
from base64 import b64decode, b64encode

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


class Encryptor:
    """Hold and use encryption functions for a specific entryption key"""

    def __init__(self, encrypt_key: str):
        self._key = encrypt_key

    @staticmethod
    def generate_hash_key(hash_str: str) -> str:
        """Create a hashed key based on sport and datetime"""
        # Create a SHA_256 hash for the combined string
        hash_object = hashlib.sha256(hash_str.encode())

        # Return the hexadecimal string of the hash. Only get the first 60 characters as the
        # fuckers at telegrem does not support longer than 64 characters and we need to add some
        # other info as well
        return hash_object.hexdigest()[:60]

    def _get_key(self) -> str:
        """Return the padded an encoded key"""
        return self._key.ljust(32)[:32].encode("utf-8")

    def encrypt_data(self, text_to_be_encripted: str) -> str:
        """Encrypt the data using the key in the object"""

        # Get the encription key from the environment
        key = self._get_key()

        # Use the cipher with AES algorithm in CBC mode and add a random IV
        rand_iv = os.urandom(16)
        cipher = Cipher(algorithms.AES(key), modes.CBC(rand_iv), backend=default_backend())
        encryptor = cipher.encryptor()

        # pad the plaintext such that it becomes a multiple of the wanted block size
        padder = padding.PKCS7(128).padder()
        padded_data = (
            padder.update(text_to_be_encripted.encode("utf-8")) + padder.finalize()
        )

        # Encrypt the padded data
        ciphertext = encryptor.update(padded_data) + encryptor.finalize()

        # Return the IV and the ciphertext, for easy storage
        return b64encode(rand_iv + ciphertext).decode("utf-8")

    def decrypt_data(self, encrypted_data: str) -> str:
        """Decrypt the object as given earlier"""

        # Get the encription key from the environment
        key = self._get_key()

        # Decode the base64-encoded text
        ciphertext = b64decode(encrypted_data)

        # split the data in the random string and the actual encrypted text
        rand_iv, actual_ciphertext = ciphertext[:16], ciphertext[16:]

        # Now create the right decryptor objects to decrypt the text
        cipher = Cipher(algorithms.AES(key), modes.CBC(rand_iv), backend=default_backend())
        decryptor = cipher.decryptor()

        # Decrypt the actual decrypted text
        padded_plaintext = decryptor.update(actual_ciphertext) + decryptor.finalize()

        # Now unpadd the text
        unpadder = padding.PKCS7(128).unpadder()
        plaintext = unpadder.update(padded_plaintext) + unpadder.finalize()

        return plaintext.decode("utf-8")
