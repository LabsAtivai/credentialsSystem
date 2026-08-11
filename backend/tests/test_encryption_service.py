import base64

import pytest

from app.services.encryption import DecryptionError, EncryptionService

VALID_KEY = base64.b64decode(base64.b64encode(b"1" * 32))


def make_service() -> EncryptionService:
    return EncryptionService(key=VALID_KEY)


def test_encrypt_decrypt_roundtrip():
    service = make_service()
    plaintext = "senha-super-secreta-123"

    token = service.encrypt(plaintext)

    assert token != plaintext
    assert service.decrypt(token) == plaintext


def test_encrypt_produces_different_ciphertext_each_time():
    service = make_service()
    token_a = service.encrypt("mesmo-valor")
    token_b = service.encrypt("mesmo-valor")

    assert token_a != token_b  # nonce aleatório por operação


def test_decrypt_rejects_tampered_ciphertext():
    service = make_service()
    token = service.encrypt("valor-original")

    raw = bytearray(base64.b64decode(token))
    raw[-1] ^= 0xFF  # corrompe o último byte (parte do auth tag)
    tampered = base64.b64encode(bytes(raw)).decode()

    with pytest.raises(DecryptionError):
        service.decrypt(tampered)


def test_decrypt_rejects_malformed_token():
    service = make_service()

    with pytest.raises(DecryptionError):
        service.decrypt("isto-nao-e-base64-valido-!!!")


def test_decrypt_rejects_empty_token():
    service = make_service()

    with pytest.raises(DecryptionError):
        service.decrypt("")


def test_service_rejects_key_with_wrong_length():
    with pytest.raises(ValueError):
        EncryptionService(key=b"chave-muito-curta")


def test_hash_for_lookup_is_deterministic_and_case_insensitive():
    service = make_service()

    a = service.hash_for_lookup("Conta@Exemplo.com")
    b = service.hash_for_lookup("  conta@exemplo.com  ")

    assert a == b
    assert len(a) == 64  # hex de sha256


def test_hash_for_lookup_differs_for_different_values():
    service = make_service()

    assert service.hash_for_lookup("a@a.com") != service.hash_for_lookup("b@b.com")
