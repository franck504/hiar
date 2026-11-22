"""Chiffrement et protection des données sensibles au repos (RGPD Art. 9).

Fournit un chiffrement symétrique fort (AES-128-CBC + HMAC-SHA256 via Fernet)
dérivé d'une clé de sécurité locale configurée dans `.env`.
"""

import base64
import hashlib
import os
from typing import Optional
from cryptography.fernet import Fernet, InvalidToken


def _get_fernet_key() -> bytes:
    """Dérive une clé Fernet valide 32-octets base64 depuis l'environnement."""
    raw_key = os.environ.get(
        "HIAR_DB_ENCRYPTION_KEY", "hiar_default_vault_secret_key_rgpd_2026"
    )
    digest = hashlib.sha256(raw_key.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt_sensitive_data(plain_text: Optional[str]) -> str:
    """Chiffre une donnée sensible au repos."""
    if not plain_text or not isinstance(plain_text, str):
        return ""
    f = Fernet(_get_fernet_key())
    token = f.encrypt(plain_text.encode("utf-8")).decode("utf-8")
    return f"ENC:{token}"


def decrypt_sensitive_data(cipher_text: Optional[str]) -> str:
    """Déchiffre une donnée chiffrée (préfixée par 'ENC:')."""
    if not cipher_text or not isinstance(cipher_text, str):
        return ""
    if not cipher_text.startswith("ENC:"):
        return cipher_text
    f = Fernet(_get_fernet_key())
    try:
        raw_token = cipher_text[4:]
        return f.decrypt(raw_token.encode("utf-8")).decode("utf-8")
    except (InvalidToken, Exception):
        return cipher_text
