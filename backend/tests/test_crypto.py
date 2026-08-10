"""Round-trip + tamper-detection tests for app/core/crypto.py."""
import pytest

from app.core.crypto import CredentialCryptoError, decrypt_credentials, encrypt_credentials


def test_round_trip_encrypt_decrypt():
    data = {"api_key": "abc123", "api_secret": "s3cr3t", "totp_secret": "JBSWY3DPEHPK3PXP"}
    blob = encrypt_credentials(data)

    assert isinstance(blob, bytes)
    # Ciphertext must not contain the plaintext secret anywhere.
    assert b"s3cr3t" not in blob

    decrypted = decrypt_credentials(blob)
    assert decrypted == data


def test_two_encryptions_of_same_data_produce_different_ciphertext():
    data = {"access_token": "same-token"}
    blob_a = encrypt_credentials(data)
    blob_b = encrypt_credentials(data)
    # Random nonce per call -> ciphertexts differ even for identical input.
    assert blob_a != blob_b
    assert decrypt_credentials(blob_a) == decrypt_credentials(blob_b) == data


def test_tampered_ciphertext_raises_instead_of_decrypting_garbage():
    blob = bytearray(encrypt_credentials({"secret": "value"}))
    # Flip a byte well past the nonce, inside the ciphertext/tag.
    blob[-1] ^= 0xFF

    with pytest.raises(CredentialCryptoError):
        decrypt_credentials(bytes(blob))


def test_truncated_blob_raises():
    with pytest.raises(CredentialCryptoError):
        decrypt_credentials(b"short")


def test_empty_blob_raises():
    with pytest.raises(CredentialCryptoError):
        decrypt_credentials(b"")
