from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Dict

import jwt
from fastapi import HTTPException
from jwt import InvalidTokenError

DEFAULT_JWT_SECRET = "fiscalhub-dev-secret-change-me"
JWT_SECRET = os.environ.get("FISCAL_AUTH_SECRET", DEFAULT_JWT_SECRET)
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = int(os.environ.get("FISCAL_AUTH_EXPIRE_HOURS", "12"))

_APP_ENV = (os.environ.get("FISCAL_ENV") or "development").strip().lower()
if _APP_ENV in {"prod", "production"}:
    if JWT_SECRET == DEFAULT_JWT_SECRET or len(JWT_SECRET) < 32:
        raise RuntimeError("Defina FISCAL_AUTH_SECRET com no minimo 32 caracteres em producao.")


def create_access_token(*, user_id: int, nome: str, role: str) -> str:
    now = datetime.now(timezone.utc)
    payload: Dict[str, object] = {
        "sub": str(int(user_id)),
        "nome": str(nome),
        "role": str(role),
        "iat": int(now.timestamp()),
        "exp": now + timedelta(hours=JWT_EXPIRE_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> Dict[str, object]:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="Token invalido ou expirado") from exc
    if "sub" not in payload:
        raise HTTPException(status_code=401, detail="Token invalido")
    return payload