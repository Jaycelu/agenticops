from __future__ import annotations

import base64
import hashlib
import json
from typing import Any

from cryptography.fernet import Fernet

from auth.session_service import auth_secret_bytes


def _cipher(purpose: str) -> Fernet:
    key = hashlib.sha256(auth_secret_bytes() + b"\x00" + purpose.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def encrypt_text(value: str, *, purpose: str) -> str:
    return _cipher(purpose).encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_text(value: str, *, purpose: str) -> str:
    return _cipher(purpose).decrypt(value.encode("ascii")).decode("utf-8")


def encrypt_json(value: dict[str, Any], *, purpose: str) -> str:
    payload = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return encrypt_text(payload, purpose=purpose)


def decrypt_json(value: str, *, purpose: str) -> dict[str, Any]:
    payload = json.loads(decrypt_text(value, purpose=purpose))
    if not isinstance(payload, dict):
        raise ValueError("encrypted payload must contain a JSON object")
    return payload
