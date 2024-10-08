"""Test module to test the Encryptor module in the src file"""

# pylint: disable=redefined-outer-name
import hashlib
from base64 import b64decode

import pytest

from usc_sign_in_bot import Encryptor  # Replace with the actual module name


@pytest.fixture
def encryptor():
    """Fixture for creating an Encryptor object."""
    key = "test_encrypt_key"
    return Encryptor(key)


def test_generate_hash_key():
    """Test generating a hash key."""
    test_str = "test_sport_2024-09-19"
    expected_hash = hashlib.sha256(test_str.encode()).hexdigest()[:60]
    assert Encryptor.generate_hash_key(test_str) == expected_hash


def test_get_key(encryptor):
    """Test if the key is correctly padded and encoded."""
    key = "test_encrypt_key"
    expected_key = key.ljust(32)[:32].encode("utf-8")
    assert encryptor._get_key() == expected_key  # pylint: disable=protected-access


def test_encrypt_data(encryptor):
    """Test encrypting data."""
    plaintext = "This is a test"
    encrypted_data = encryptor.encrypt_data(plaintext)

    # Ensure the result is a base64-encoded string
    assert isinstance(encrypted_data, str)

    decoded = b64decode(encrypted_data)
    # Ensure IV is 16 bytes
    assert len(decoded[:16]) == 16
    # Ensure ciphertext exists
    assert len(decoded[16:]) > 0


def test_decrypt_data(encryptor):
    """Test encrypting and decrypting data to ensure decryption is correct."""
    plaintext = "This is a test"
    encrypted_data = encryptor.encrypt_data(plaintext)
    decrypted_data = encryptor.decrypt_data(encrypted_data)

    assert decrypted_data == plaintext


def test_encrypt_decrypt_roundtrip(encryptor):
    """Test that encrypting and decrypting returns the original text."""
    plaintext = "Roundtrip test data"
    encrypted = encryptor.encrypt_data(plaintext)
    decrypted = encryptor.decrypt_data(encrypted)

    assert decrypted == plaintext
