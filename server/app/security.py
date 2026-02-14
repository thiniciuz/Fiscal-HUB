from __future__ import annotations

import base64
import hashlib
import hmac
import os


_ALGO = "sha256"
_ITERATIONS = 210_000
_PREFIX = "pbkdf2_sha256"


def is_password_hash(value: str) -> bool:
    raw = str(value or "").strip()
    return raw.startswith(f"{_PREFIX}$")


def hash_password(password: str) -> str:
    plain = str(password or "").strip()
    if not plain:
        raise ValueError("Senha vazia nao permitida")
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac(_ALGO, plain.encode("utf-8"), salt, _ITERATIONS)
    salt_b64 = base64.b64encode(salt).decode("ascii")
    digest_b64 = base64.b64encode(digest).decode("ascii")
    return f"{_PREFIX}${_ITERATIONS}${salt_b64}${digest_b64}"


def verify_password(password: str, stored: str) -> bool:
    raw = str(stored or "").strip()
    plain = str(password or "")
    if not raw:
        return False
    if not is_password_hash(raw):
        return hmac.compare_digest(raw, plain)
    try:
        _, iters_s, salt_b64, digest_b64 = raw.split("$", 3)
        iters = int(iters_s)
        salt = base64.b64decode(salt_b64.encode("ascii"))
        expected = base64.b64decode(digest_b64.encode("ascii"))
    except Exception:
        return False
    computed = hashlib.pbkdf2_hmac(_ALGO, plain.encode("utf-8"), salt, iters)
    return hmac.compare_digest(expected, computed)