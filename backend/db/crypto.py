"""Encryption for stored source credentials.

OAuth refresh tokens and private feed URLs are secrets. They must be
decryptable (we need to replay them), so they are encrypted at rest with
Fernet (AES-128-CBC + HMAC) rather than hashed.

The key comes from `SECRET_KEY`. In development one is derived automatically
and cached on disk; in production set it explicitly and rotate it like any
other secret.
"""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from config import SECRET_KEY, get_logger

logger = get_logger(__name__)


class DecryptionError(ValueError):
    """A stored secret could not be decrypted with the current key."""


def _derive_key(secret: str) -> bytes:
    """Fernet needs a 32-byte urlsafe-base64 key."""
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


_fernet = Fernet(_derive_key(SECRET_KEY))


def encrypt(plaintext: str) -> str:
    if plaintext is None:
        raise ValueError("Cannot encrypt None.")

    return _fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt(ciphertext: str) -> str:
    """Decrypt a stored secret.

    Raises:
        DecryptionError: if the value is corrupt or SECRET_KEY has changed.
    """
    if not ciphertext:
        raise DecryptionError("No value to decrypt.")

    try:
        return _fernet.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except (InvalidToken, ValueError) as exc:
        raise DecryptionError(
            "Stored credential could not be decrypted. It may have been "
            "encrypted with a different SECRET_KEY - reconnect the source."
        ) from exc


def try_decrypt(ciphertext: str) -> str | None:
    """Decrypt, returning None instead of raising."""
    try:
        return decrypt(ciphertext)
    except DecryptionError as exc:
        logger.warning("%s", exc)
        return None
