"""App-level envelope encryption for broker credentials at rest.

`broker_connections.encrypted_credentials` is `bytea` — we never store a
broker API key/secret/password/TOTP-seed in plaintext. This module wraps
AES-256-GCM (via the `cryptography` package) keyed by a SHA-256 digest of
`APP_SECRET_KEY` (so any string-length secret becomes a valid 32-byte key).

Wire format written to the column:  nonce(12 bytes) || ciphertext (includes
the 16-byte GCM authentication tag appended by `AESGCM.encrypt`).

Decryption only ever happens in-memory, immediately before an adapter needs
to authenticate against a real broker; callers must never log the returned
dict.
"""
from __future__ import annotations

import hashlib
import json
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import get_settings

_NONCE_SIZE = 12  # 96-bit nonce, the recommended size for AES-GCM


class CredentialCryptoError(Exception):
    """Raised when a credential blob cannot be decrypted — either it was
    tampered with, corrupted, or encrypted under a different APP_SECRET_KEY.
    Never leaks partial/garbage plaintext; always fails closed."""


def _derive_key(secret: str | None = None) -> bytes:
    raw = secret if secret is not None else get_settings().APP_SECRET_KEY
    return hashlib.sha256(raw.encode("utf-8")).digest()


def encrypt_credentials(data: dict) -> bytes:
    """Serialize `data` to JSON and encrypt it with AES-256-GCM.
    Returns the raw bytes to store directly in the `bytea` column."""
    key = _derive_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(_NONCE_SIZE)
    plaintext = json.dumps(data).encode("utf-8")
    ciphertext = aesgcm.encrypt(nonce, plaintext, associated_data=None)
    return nonce + ciphertext


def decrypt_credentials(blob: bytes) -> dict:
    """Decrypt a blob produced by `encrypt_credentials`. Raises
    `CredentialCryptoError` (never returns silently-wrong data) if the blob
    is too short, was encrypted under a different key, or has been tampered
    with (GCM tag mismatch)."""
    if not blob or len(blob) <= _NONCE_SIZE:
        raise CredentialCryptoError("Encrypted credential blob is missing or truncated.")
    key = _derive_key()
    aesgcm = AESGCM(key)
    nonce, ciphertext = blob[:_NONCE_SIZE], blob[_NONCE_SIZE:]
    try:
        plaintext = aesgcm.decrypt(nonce, ciphertext, associated_data=None)
    except InvalidTag as exc:
        raise CredentialCryptoError(
            "Credential blob failed authentication — it was tampered with, "
            "corrupted, or encrypted under a different APP_SECRET_KEY."
        ) from exc
    try:
        return json.loads(plaintext.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise CredentialCryptoError("Decrypted credential payload is not valid JSON.") from exc
