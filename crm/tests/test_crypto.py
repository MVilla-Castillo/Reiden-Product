"""Tests para el módulo de cifrado crypto."""

import pytest
from cryptography.fernet import Fernet
from django.test import override_settings

from core.crypto import (
    EncryptionKeyMissingError,
    decrypt,
    encrypt,
    generate_key,
    reset_fernet,
)


def test_generate_key_returns_valid_fernet_key() -> None:
    key = generate_key()
    Fernet(key.encode("utf-8"))


@pytest.mark.django_db
@override_settings(WA_ID_ENCRYPTION_KEY=generate_key())
def test_encrypt_and_decrypt_roundtrip() -> None:
    reset_fernet()
    plaintext = "56912345678"
    ciphertext = encrypt(plaintext)
    assert ciphertext != plaintext
    assert decrypt(ciphertext) == plaintext


@pytest.mark.django_db
@override_settings(WA_ID_ENCRYPTION_KEY="")
def test_encrypt_raises_without_key() -> None:
    reset_fernet()
    with pytest.raises(EncryptionKeyMissingError):
        encrypt("secret")


@pytest.mark.django_db
@override_settings(WA_ID_ENCRYPTION_KEY="")
def test_decrypt_raises_without_key() -> None:
    reset_fernet()
    with pytest.raises(EncryptionKeyMissingError):
        decrypt("anything")


@pytest.mark.django_db
@override_settings(WA_ID_ENCRYPTION_KEY=generate_key())
def test_decrypt_raises_on_invalid_token() -> None:
    reset_fernet()
    with pytest.raises(Exception):
        decrypt("not-a-valid-fernet-token")
