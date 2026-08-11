import base64
import hashlib
import hmac
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config import settings

_NONCE_SIZE = 12  # 96 bits, tamanho recomendado para AES-GCM


class DecryptionError(Exception):
    pass


class EncryptionService:
    """Criptografia reversível (AES-256-GCM) para credenciais sensíveis.

    Formato armazenado: base64(nonce[12 bytes] || ciphertext || auth_tag[16 bytes]).
    Nonce gerado aleatoriamente a cada chamada — nunca reutilizado com a mesma chave.
    """

    def __init__(self, key: bytes | None = None) -> None:
        self._key = key if key is not None else settings.encryption_key_bytes
        if len(self._key) != 32:
            raise ValueError("Chave de criptografia deve ter 32 bytes (AES-256).")
        self._aesgcm = AESGCM(self._key)

    def encrypt(self, plaintext: str) -> str:
        if plaintext is None:
            raise ValueError("plaintext não pode ser None.")
        nonce = os.urandom(_NONCE_SIZE)
        ciphertext = self._aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
        return base64.b64encode(nonce + ciphertext).decode("ascii")

    def decrypt(self, token: str) -> str:
        if not token:
            raise DecryptionError("Token de criptografia vazio ou ausente.")
        try:
            raw = base64.b64decode(token, validate=True)
        except Exception as exc:
            raise DecryptionError("Token de criptografia malformado.") from exc

        if len(raw) < _NONCE_SIZE:
            raise DecryptionError("Token de criptografia inválido.")

        nonce, ciphertext = raw[:_NONCE_SIZE], raw[_NONCE_SIZE:]
        try:
            plaintext = self._aesgcm.decrypt(nonce, ciphertext, None)
        except InvalidTag as exc:
            raise DecryptionError(
                "Falha na autenticação do dado criptografado (tag inválida — dado corrompido ou adulterado)."
            ) from exc
        return plaintext.decode("utf-8")

    def hash_for_lookup(self, value: str) -> str:
        """HMAC-SHA256 determinístico para comparação de unicidade sem expor plaintext."""
        normalized = value.strip().lower().encode("utf-8")
        return hmac.new(self._key, normalized, hashlib.sha256).hexdigest()


encryption_service = EncryptionService()
