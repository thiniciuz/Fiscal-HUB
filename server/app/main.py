from __future__ import annotations

from typing import Optional, List
from datetime import date, timedelta
import calendar
import io
import os
import re
import time

import pdfplumber
from fastapi import FastAPI, UploadFile, File, HTTPException, Query, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from .db import init_db, _connect
from .schemas import (
    UserOut,
    UserCreate,
    UserRoleUpdate,
    UserLogin,
    AuthLoginOut,
    CompanyOut,
    CompanyCreate,
    CompanyUpdate,
    TaskOut,
    TaskCreate,
    TaskStatusUpdate,
    TaskUpdate,
    TaskLogOut,
    TaskCommentOut,
    TaskCommentCreate,
    NotificationOut,
    ServerSettingsOut,
    ServerSettingsUpdate,
    EmailSettingsOut,
    EmailSettingsUpdate,
)
from .repositories import (
    UserRepository,
    CompanyRepository,
    TaskRepository,
    ClassificationRepository,
    TaskLogRepository,
    TaskCommentRepository,
    NotificationRepository,
    SettingsRepository,
)
from .classifier import classify_filename, save_classification_json
from .auth import create_access_token, decode_access_token


_LAST_MONTHLY_SYNC: Optional[str] = None


def _read_env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


MAX_PDF_MB = max(1, _read_env_int("FISCAL_MAX_PDF_MB", 10))
MAX_PDF_BYTES = MAX_PDF_MB * 1024 * 1024

LOGIN_WINDOW_SECONDS = max(30, _read_env_int("FISCAL_LOGIN_WINDOW_SECONDS", 300))
LOGIN_MAX_ATTEMPTS = max(3, _read_env_int("FISCAL_LOGIN_MAX_ATTEMPTS", 8))
_LOGIN_ATTEMPTS: dict[str, dict[str, float]] = {}


def _cors_origins() -> list[str]:
    defaults = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://tauri.localhost",
        "http://tauri.localhost",
        "tauri://localhost",
    ]
    raw = str(os.environ.get("FISCAL_CORS_ORIGINS") or "").strip()
    if not raw:
        return defaults
    extras = [item.strip() for item in raw.split(",") if item.strip()]
    out: list[str] = []
    for origin in defaults + extras:
        if origin not in out:
            out.append(origin)
    return out


def _easter_sunday(year: int) -> date:
    # Meeus/Jones/Butcher
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def _br_holidays(year: int) -> set[date]:
    easter = _easter_sunday(year)
    fixed = {
        date(year, 1, 1),
        date(year, 4, 21),
        date(year, 5, 1),
        date(year, 9, 7),
        date(year, 10, 12),
        date(year, 11, 2),
        date(year, 11, 15),
        date(year, 12, 25),
    }
    movable = {
        easter - timedelta(days=48),  # carnaval (seg)
        easter - timedelta(days=47),  # carnaval (ter)
        easter - timedelta(days=2),   # sexta-feira santa
        easter + timedelta(days=60),  # corpus christi
    }
    return fixed | movable


def _prev_business_day(dt: date, holidays: set[date]) -> date:
    out = dt
    while out.weekday() >= 5 or out in holidays:
        out -= timedelta(days=1)
    return out


def _shift_year_month(year: int, month: int, offset: int) -> tuple[int, int]:
    m = month + offset
    y = year
    while m > 12:
        m -= 12
        y += 1
    while m < 1:
        m += 12
        y -= 1
    return y, m


def _sync_monthly_tasks_for(year: int, month: int) -> None:
    competencia = f"{year}{month:02d}"
    holidays = _br_holidays(year)
    last_day = calendar.monthrange(year, month)[1]

    fed_rules = [
        ("OBR", "FED", "DARF PIS", 25, 0),
        ("OBR", "FED", "DARF COFINS", 25, 0),
        ("OBR", "FED", "DARF IPI", 20, 0),
        ("OBR", "FED", "DARF CSRF", 20, 0),
        ("OBR", "FED", "DARF IRRF", 20, 0),
        ("OBR", "FED", "DARF INSS", 20, 0),
        ("OBR", "FED", "DARF IRPJ", None, 0),  # último dia útil do mês
        ("OBR", "FED", "DARF CSLL", None, 0),  # último dia útil do mês
        ("ACS", "FED", "SPED CONTRIBUIÇÕES", 10, 1),  # mês posterior
        ("ACS", "FED", "MIT - DCTFWEB", None, 0),     # último dia útil do mês
        ("ACS", "FED", "REINF", 15, 0),
    ]
    est_rules = [
        ("OBR", "EST", "GR PR ICMS", 12, 0),
        ("OBR", "EST", "DARE SP ICMS", 20, 0),
        ("OBR", "EST", "DARE SC ICMS", 10, 0),
        ("OBR", "EST", "DUA ES ICMS", 25, 0),
        ("OBR", "EST", "DAE MG ICMS", 8, 0),
        ("OBR", "EST", "GA RS ICMS", 15, 0),
        ("ACS", "EST", "SPED FISCAL", 20, 0),
        ("ACS", "EST", "DAPI", 8, 0),
        ("ACS", "EST", "DIME", 10, 0),
        ("ACS", "EST", "GIA", 15, 0),
        ("ACS", "EST", "DeSTDA", None, 0),  # último dia útil do mês
    ]
    rules = fed_rules + est_rules

    conn = _connect()
    cur = conn.cursor()
    companies = cur.execute(
        "SELECT id, user_id, responsavel_id FROM empresas ORDER BY id"
    ).fetchall()

    for company in companies:
        company_id = int(company["id"])
        owner_id = int(company["responsavel_id"] or company["user_id"])
        for tipo, orgao, tributo, due_day, month_offset in rules:
            due_year, due_month = _shift_year_month(year, month, month_offset)
            due_holidays = holidays if due_year == year else _br_holidays(due_year)
            due_last_day = calendar.monthrange(due_year, due_month)[1]
            base_day = due_last_day if due_day is None else due_day
            venc = _prev_business_day(date(due_year, due_month, base_day), due_holidays).isoformat()

            row = cur.execute(
                """
                SELECT id, titulo, vencimento, user_id
                FROM tarefas
                WHERE company_id = ? AND competencia = ? AND tipo = ? AND orgao = ?
                  AND TRIM(tributo) = TRIM(?)
                LIMIT 1
                """,
                (company_id, competencia, tipo, orgao, tributo),
            ).fetchone()

            if row:
                if (
                    str(row["titulo"] or "") != tributo
                    or str(row["vencimento"] or "") != venc
                    or int(row["user_id"] or 0) != owner_id
                ):
                    cur.execute(
                        """
                        UPDATE tarefas
                        SET user_id = ?, titulo = ?, vencimento = ?
                        WHERE id = ?
                        """,
                        (owner_id, tributo, venc, int(row["id"])),
                    )
            else:
                cur.execute(
                    """
                    INSERT INTO tarefas (user_id, company_id, titulo, tipo, orgao, tributo, competencia, vencimento, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'PENDENTE')
                    """,
                    (owner_id, company_id, tributo, tipo, orgao, tributo, competencia, venc),
                )

    conn.commit()
    conn.close()


def _ensure_monthly_tasks_synced() -> None:
    global _LAST_MONTHLY_SYNC
    today = date.today()
    comp = f"{today.year}{today.month:02d}"
    if _LAST_MONTHLY_SYNC == comp:
        return
    _sync_monthly_tasks_for(today.year, today.month)
    _LAST_MONTHLY_SYNC = comp


def _get_role(user_id: int) -> str:
    repo = UserRepository()
    users = repo.list()
    for u in users:
        if int(u["id"]) == int(user_id):
            return str(u.get("role") or "collab")
    return "collab"


def _can_view_all(role: str) -> bool:
    return role in {"admin", "manager"}


def _can_edit(role: str) -> bool:
    return role in {"admin", "collab"}



def _normalize_cnpj(value: str) -> Optional[str]:
    digits = re.sub(r"\D", "", value or "")
    return digits if len(digits) == 14 else None


def _extract_pdf_text(data: bytes) -> str:
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            parts = []
            for page in pdf.pages:
                parts.append(page.extract_text() or "")
            return "\n".join(parts)
    except Exception:
        return ""


def _find_cnpj(text: str) -> Optional[str]:
    if not text:
        return None
    match = re.search(r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b", text)
    if match:
        return _normalize_cnpj(match.group(0))
    match = re.search(r"\b\d{14}\b", text)
    if match:
        return _normalize_cnpj(match.group(0))
    return None


def _find_competencia(text: str) -> Optional[str]:
    if not text:
        return None
    match = re.search(r"\b(0[1-9]|1[0-2])[/-](\d{4})\b", text)
    if not match:
        return None
    mm, yyyy = match.group(1), match.group(2)
    return f"{yyyy}{mm}"


def _match_tributo(text: str, tributo: Optional[str]) -> Optional[bool]:
    if not tributo:
        return None
    hay = (text or "").lower()
    needle = tributo.lower().strip()
    if not needle:
        return None
    return needle in hay

bearer_scheme = HTTPBearer(auto_error=False)
_PUBLIC_PATHS = {"/health", "/auth/login"}
_PUBLIC_PREFIXES = ("/docs", "/redoc", "/openapi.json")


def _build_auth_user_from_payload(payload: dict) -> dict:
    user_id = int(payload.get("sub") or 0)
    user = UserRepository().get(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="Usuario do token nao encontrado")
    return {
        "id": int(user["id"]),
        "nome": str(user["nome"]),
        "role": str(user.get("role") or "collab"),
        "is_default": bool(user.get("is_default")),
    }


def _optional_auth_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme)) -> Optional[dict]:
    if credentials is None:
        return None
    payload = decode_access_token(credentials.credentials)
    return _build_auth_user_from_payload(payload)

def _require_auth_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme)) -> dict:
    auth_user = _optional_auth_user(credentials)
    if not auth_user:
        raise HTTPException(status_code=401, detail="Autenticação obrigatória")
    return auth_user


def _require_admin_user(auth_user: dict) -> None:
    if str(auth_user.get("role") or "") != "admin":
        raise HTTPException(status_code=403, detail="Apenas admin pode executar esta ação.")


def _resolve_query_user_id(auth_user: dict, requested_user_id: Optional[int]) -> int:
    actor_id = int(auth_user["id"])
    if requested_user_id is None:
        return actor_id
    requested = int(requested_user_id)
    if requested == actor_id:
        return actor_id
    if str(auth_user.get("role") or "") == "admin":
        return requested
    raise HTTPException(status_code=403, detail="Sem permissão para atuar em nome de outro usuário.")


def _login_attempt_key(request: Request, nome: str) -> str:
    forwarded = str(request.headers.get("x-forwarded-for") or "").split(",", 1)[0].strip()
    host = forwarded or (request.client.host if request.client else "unknown")
    login_name = str(nome or "").strip().lower()
    return f"{host}:{login_name}"


def _is_login_rate_limited(key: str) -> bool:
    entry = _LOGIN_ATTEMPTS.get(key)
    if not entry:
        return False
    now = time.time()
    if now - entry["first"] > LOGIN_WINDOW_SECONDS:
        _LOGIN_ATTEMPTS.pop(key, None)
        return False
    return entry["count"] >= LOGIN_MAX_ATTEMPTS


def _register_login_failure(key: str) -> None:
    now = time.time()
    entry = _LOGIN_ATTEMPTS.get(key)
    if (not entry) or (now - entry["first"] > LOGIN_WINDOW_SECONDS):
        _LOGIN_ATTEMPTS[key] = {"first": now, "count": 1}
        return
    entry["count"] += 1


def _clear_login_failures(key: str) -> None:
    _LOGIN_ATTEMPTS.pop(key, None)


app = FastAPI(title="41 Fiscal Hub API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def auth_guard(request: Request, call_next):
    method = request.method.upper()
    path = (request.url.path or "/").rstrip("/") or "/"

    if method == "OPTIONS":
        return await call_next(request)

    if path in _PUBLIC_PATHS or any(path.startswith(prefix) for prefix in _PUBLIC_PREFIXES):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        return response

    if path == "/users" and method == "POST" and UserRepository().count() == 0:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        return response

    auth_header = str(request.headers.get("authorization") or "")
    if not auth_header.lower().startswith("bearer "):
        return JSONResponse(status_code=401, content={"detail": "Autenticacao obrigatoria"})

    token = auth_header.split(" ", 1)[1].strip()
    if not token:
        return JSONResponse(status_code=401, content={"detail": "Token ausente"})

    try:
        payload = decode_access_token(token)
        request.state.auth_user = _build_auth_user_from_payload(payload)
    except HTTPException as exc:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    return response


@app.on_event("startup")
def _startup() -> None:
    init_db()
    UserRepository().migrate_plaintext_passwords()
    _ensure_monthly_tasks_synced()


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/maintenance/sync-monthly")
def maintenance_sync_monthly(
    user_id: Optional[int] = Query(None),
    year: Optional[int] = Query(None),
    month: Optional[int] = Query(None),
    auth_user: dict = Depends(_require_auth_user),
):
    _require_admin_user(auth_user)
    _resolve_query_user_id(auth_user, user_id)
    if (year is None) != (month is None):
        raise HTTPException(status_code=400, detail="Informe ano e mês juntos, ou nenhum.")
    if year is None and month is None:
        today = date.today()
        year, month = today.year, today.month
    if not (1 <= int(month) <= 12):
        raise HTTPException(status_code=400, detail="Mês inválido.")
    _sync_monthly_tasks_for(int(year), int(month))
    global _LAST_MONTHLY_SYNC
    _LAST_MONTHLY_SYNC = f"{int(year)}{int(month):02d}"
    return {"ok": True, "competencia": _LAST_MONTHLY_SYNC}


@app.get("/users", response_model=List[UserOut])
def list_users(auth_user: dict = Depends(_require_auth_user)):
    if auth_user["role"] not in {"admin", "manager"}:
        raise HTTPException(status_code=403, detail="Sem permissão para listar usuários.")
    repo = UserRepository()
    rows = repo.list()
    return [
        {
            **r,
            "is_default": bool(r.get("is_default")),
        }
        for r in rows
    ]


@app.post("/users", response_model=UserOut)
def create_user(payload: UserCreate, auth_user: Optional[dict] = Depends(_optional_auth_user)):
    repo = UserRepository()
    senha = str(payload.senha or "").strip()
    if len(senha) < 8:
        raise HTTPException(status_code=400, detail="Senha deve ter no minimo 8 caracteres.")

    if repo.count() == 0:
        role = payload.role if payload.role in {"admin", "manager", "collab"} else "admin"
        new_id = repo.create(payload.nome, role=role, is_default=True, senha=senha)
        return {"id": new_id, "nome": payload.nome, "role": role, "is_default": True}

    if not auth_user:
        raise HTTPException(status_code=401, detail="Autenticação obrigatória")
    _require_admin_user(auth_user)

    new_id = repo.create(payload.nome, role=payload.role, is_default=payload.is_default, senha=senha)
    return {"id": new_id, "nome": payload.nome, "role": payload.role, "is_default": payload.is_default}


@app.post("/auth/login", response_model=AuthLoginOut)
def login(payload: UserLogin, request: Request):
    attempt_key = _login_attempt_key(request, payload.nome)
    if _is_login_rate_limited(attempt_key):
        raise HTTPException(status_code=429, detail="Muitas tentativas. Aguarde e tente novamente.")

    repo = UserRepository()
    user = repo.verify_login(payload.nome, payload.senha)
    if not user:
        _register_login_failure(attempt_key)
        raise HTTPException(status_code=401, detail="Credenciais inválidas")

    _clear_login_failures(attempt_key)
    user_out = {
        "id": int(user["id"]),
        "nome": str(user["nome"]),
        "role": str(user.get("role") or "collab"),
        "is_default": bool(user.get("is_default")),
    }
    token = create_access_token(
        user_id=int(user_out["id"]),
        nome=str(user_out["nome"]),
        role=str(user_out["role"]),
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user_out,
    }


@app.post("/users/{user_id}/default")
def set_default_user(user_id: int, auth_user: dict = Depends(_require_auth_user)):
    _require_admin_user(auth_user)
    repo = UserRepository()
    repo.set_default(user_id)
    return {"ok": True}


@app.patch("/users/{user_id}/role")
def update_user_role(user_id: int, payload: UserRoleUpdate, auth_user: dict = Depends(_require_auth_user)):
    _require_admin_user(auth_user)
    if payload.role not in {"admin", "manager", "collab"}:
        raise HTTPException(status_code=400, detail="Role inválida")
    repo = UserRepository()
    repo.update_role(user_id, payload.role)
    return {"ok": True}


@app.get("/settings/server", response_model=ServerSettingsOut)
def get_server_settings(user_id: Optional[int] = Query(None), auth_user: dict = Depends(_require_auth_user)):
    _require_admin_user(auth_user)
    _resolve_query_user_id(auth_user, user_id)
    repo = SettingsRepository()
    return repo.get_server()


@app.patch("/settings/server", response_model=ServerSettingsOut)
def update_server_settings(payload: ServerSettingsUpdate, user_id: Optional[int] = Query(None), auth_user: dict = Depends(_require_auth_user)):
    _require_admin_user(auth_user)
    _resolve_query_user_id(auth_user, user_id)
    repo = SettingsRepository()
    return repo.set_server(payload.model_dump())


@app.get("/settings/email", response_model=EmailSettingsOut)
def get_email_settings(user_id: Optional[int] = Query(None), auth_user: dict = Depends(_require_auth_user)):
    _require_admin_user(auth_user)
    _resolve_query_user_id(auth_user, user_id)
    repo = SettingsRepository()
    return repo.get_email()


@app.patch("/settings/email", response_model=EmailSettingsOut)
def update_email_settings(payload: EmailSettingsUpdate, user_id: Optional[int] = Query(None), auth_user: dict = Depends(_require_auth_user)):
    _require_admin_user(auth_user)
    _resolve_query_user_id(auth_user, user_id)
    repo = SettingsRepository()
    return repo.set_email(payload.model_dump())


@app.get("/companies", response_model=List[CompanyOut])
def list_companies(
    request: Request,
    user_id: Optional[int] = Query(None),
    query: str = "",
    regime: Optional[str] = None,
    competencia: Optional[str] = None,
):
    _ensure_monthly_tasks_synced()
    repo = CompanyRepository()
    auth_user = request.state.auth_user
    scope_user_id = _resolve_query_user_id(auth_user, user_id)
    role = str(auth_user.get("role") or "collab")

    responsavel_id: Optional[int] = None
    list_user_id: Optional[int] = scope_user_id
    if _can_view_all(role):
        list_user_id = None
    else:
        responsavel_id = scope_user_id
        list_user_id = None

    return repo.list(
        list_user_id,
        responsavel_id=responsavel_id,
        query=query,
        regime=regime,
        competencia=competencia,
    )


@app.post("/companies", response_model=CompanyOut)
def create_company(payload: CompanyCreate, request: Request):
    auth_user = request.state.auth_user
    actor_id = int(auth_user["id"])
    role = str(auth_user.get("role") or "collab")

    if role == "manager":
        raise HTTPException(status_code=403, detail="Manager não pode criar empresas.")
    if role in {"admin", "manager"} and payload.responsavel_id is None:
        raise HTTPException(status_code=400, detail="responsavel_id é obrigatório")
    if role == "collab":
        if payload.responsavel_id is not None and int(payload.responsavel_id) != actor_id:
            raise HTTPException(status_code=403, detail="Collab não pode atribuir outro responsável.")
        payload.responsavel_id = actor_id

    repo = CompanyRepository()
    new_id = repo.create(
        user_id=actor_id,
        nome=payload.nome,
        cnpj=payload.cnpj,
        ie=payload.ie,
        regime=payload.regime,
        observacoes=payload.observacoes,
        data_entrada=payload.data_entrada,
        data_saida=payload.data_saida,
        responsavel_id=payload.responsavel_id,
    )
    created = repo.get(new_id)
    return created or {
        "id": new_id,
        "nome": payload.nome,
        "cnpj": payload.cnpj,
        "ie": payload.ie,
        "regime": payload.regime,
        "observacoes": payload.observacoes if isinstance(payload.observacoes, list) else [payload.observacoes],
        "data_entrada": payload.data_entrada,
        "data_saida": payload.data_saida,
        "responsavel_id": payload.responsavel_id,
    }


@app.patch("/companies/{company_id}", response_model=CompanyOut)
def update_company(company_id: int, payload: CompanyUpdate, request: Request, user_id: Optional[int] = Query(None)):
    auth_user = request.state.auth_user
    actor_id = _resolve_query_user_id(auth_user, user_id)
    role = str(auth_user.get("role") or "collab")

    if role == "manager":
        raise HTTPException(status_code=403, detail="Manager não pode editar empresas.")
    if role == "collab":
        if payload.responsavel_id is not None and int(payload.responsavel_id) != int(actor_id):
            raise HTTPException(status_code=403, detail="Collab não pode atribuir outro responsável.")

    repo = CompanyRepository()
    repo.update(
        user_id=None if role == "admin" else actor_id,
        company_id=company_id,
        nome=payload.nome,
        cnpj=payload.cnpj,
        ie=payload.ie,
        regime=payload.regime,
        observacoes=payload.observacoes,
        data_entrada=payload.data_entrada,
        data_saida=payload.data_saida,
        responsavel_id=payload.responsavel_id,
    )
    updated = repo.get(company_id)
    return updated or {
        "id": company_id,
        "nome": payload.nome,
        "cnpj": payload.cnpj,
        "ie": payload.ie,
        "regime": payload.regime,
        "observacoes": payload.observacoes if isinstance(payload.observacoes, list) else [payload.observacoes],
        "data_entrada": payload.data_entrada,
        "data_saida": payload.data_saida,
        "responsavel_id": payload.responsavel_id,
    }


@app.patch("/companies/{company_id}/responsavel", response_model=CompanyOut)
def update_company_responsavel(company_id: int, payload: dict, request: Request, user_id: Optional[int] = Query(None)):
    auth_user = request.state.auth_user
    _resolve_query_user_id(auth_user, user_id)
    role = str(auth_user.get("role") or "collab")

    if role not in {"admin", "manager"}:
        raise HTTPException(status_code=403, detail="Sem permissão para trocar responsável.")
    responsavel_id = payload.get("responsavel_id")
    if responsavel_id is None:
        raise HTTPException(status_code=400, detail="responsavel_id é obrigatório")

    repo = CompanyRepository()
    repo.update_responsavel(company_id, int(responsavel_id))
    updated = repo.get(company_id)
    if not updated:
        raise HTTPException(status_code=404, detail="Empresa não encontrada.")
    return updated


@app.get("/tasks", response_model=List[TaskOut])
def list_tasks(
    request: Request,
    user_id: Optional[int] = Query(None),
    company_id: Optional[int] = None,
    status: Optional[List[str]] = Query(None),
    tipo: Optional[str] = None,
    competencia: Optional[str] = None,
):
    _ensure_monthly_tasks_synced()
    repo = TaskRepository()

    auth_user = request.state.auth_user
    scope_user_id = _resolve_query_user_id(auth_user, user_id)
    role = str(auth_user.get("role") or "collab")
    list_user_id = None if _can_view_all(role) else scope_user_id

    rows = repo.list(
        user_id=list_user_id,
        company_id=company_id,
        status=status,
        tipo=tipo,
        competencia=competencia,
    )
    return [
        {
            **r,
            "has_pdf": bool(r.get("has_pdf")),
        }
        for r in rows
    ]


@app.get("/tasks/upcoming", response_model=List[TaskOut])
def list_upcoming_tasks(
    request: Request,
    user_id: Optional[int] = Query(None),
    days: int = 7,
    prev_competencia: bool = False,
):
    _ensure_monthly_tasks_synced()
    repo = TaskRepository()

    auth_user = request.state.auth_user
    scope_user_id = _resolve_query_user_id(auth_user, user_id)
    role = str(auth_user.get("role") or "collab")
    list_user_id = None if _can_view_all(role) else scope_user_id

    competencia = None
    if prev_competencia:
        today = date.today()
        year = today.year
        month = today.month - 1
        if month <= 0:
            month = 12
            year -= 1
        competencia = f"{year}{str(month).zfill(2)}"

    rows = repo.list_upcoming(user_id=list_user_id, days=days, competencia=competencia)
    return [
        {
            **r,
            "has_pdf": bool(r.get("has_pdf")),
        }
        for r in rows
    ]


@app.post("/tasks", response_model=TaskOut)
def create_task(payload: TaskCreate, request: Request):
    auth_user = request.state.auth_user
    actor_id = int(auth_user["id"])
    role = str(auth_user.get("role") or "collab")

    if role == "manager":
        raise HTTPException(status_code=403, detail="Manager não pode criar tarefas.")

    target_user_id = actor_id
    if role == "admin" and payload.user_id:
        target_user_id = int(payload.user_id)

    repo = TaskRepository()
    new_id = repo.create(
        user_id=target_user_id,
        company_id=payload.company_id,
        titulo=payload.titulo,
        tipo=payload.tipo,
        orgao=payload.orgao,
        tributo=payload.tributo,
        competencia=payload.competencia,
        vencimento=payload.vencimento,
        status=payload.status,
    )
    return {
        "id": new_id,
        "company_id": payload.company_id,
        "titulo": payload.titulo,
        "tipo": payload.tipo,
        "orgao": payload.orgao,
        "tributo": payload.tributo,
        "competencia": payload.competencia,
        "status": payload.status,
        "pdf_path": None,
        "has_pdf": False,
    }


@app.patch("/tasks/{task_id}/status")
def update_status(task_id: int, payload: TaskStatusUpdate, request: Request, user_id: Optional[int] = Query(None)):
    auth_user = request.state.auth_user
    scope_user_id = _resolve_query_user_id(auth_user, user_id)
    role = str(auth_user.get("role") or "collab")

    if role == "manager":
        raise HTTPException(status_code=403, detail="Manager não pode editar tarefas.")

    repo = TaskRepository()
    old = repo.get(task_id, None if role == "admin" else scope_user_id)
    if not old:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada.")

    repo.update_status(task_id, None if role == "admin" else scope_user_id, payload.status)
    TaskLogRepository().create(
        task_id=task_id,
        user_id=scope_user_id,
        action="status",
        details=f"{old.get('status')} -> {payload.status}",
    )
    return {"ok": True}


@app.patch("/tasks/{task_id}", response_model=TaskOut)
def update_task(task_id: int, payload: TaskUpdate, request: Request, user_id: Optional[int] = Query(None)):
    auth_user = request.state.auth_user
    scope_user_id = _resolve_query_user_id(auth_user, user_id)
    role = str(auth_user.get("role") or "collab")

    if role == "manager":
        raise HTTPException(status_code=403, detail="Manager não pode editar tarefas.")

    repo = TaskRepository()
    old = repo.get(task_id, None if role == "admin" else scope_user_id)
    if not old:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada.")

    repo.update(
        task_id=task_id,
        user_id=None if role == "admin" else scope_user_id,
        titulo=payload.titulo,
        tipo=payload.tipo,
        orgao=payload.orgao,
        tributo=payload.tributo,
        competencia=payload.competencia,
        vencimento=payload.vencimento,
        status=payload.status,
    )

    changes = []
    for field in ["titulo", "tipo", "orgao", "tributo", "competencia", "vencimento", "status"]:
        if str(old.get(field) or "") != str(getattr(payload, field) or ""):
            changes.append(f"{field}: {old.get(field)} -> {getattr(payload, field)}")

    TaskLogRepository().create(
        task_id=task_id,
        user_id=scope_user_id,
        action="update",
        details=("; ".join(changes) if changes else "sem mudanças"),
    )
    return repo.get(task_id, None if role == "admin" else scope_user_id)


@app.post("/tasks/{task_id}/pdf")
async def upload_pdf(task_id: int, request: Request, user_id: Optional[int] = Query(None), file: UploadFile = File(...)):
    auth_user = request.state.auth_user
    scope_user_id = _resolve_query_user_id(auth_user, user_id)
    role = str(auth_user.get("role") or "collab")

    if role == "manager":
        raise HTTPException(status_code=403, detail="Manager não pode editar tarefas.")
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Somente PDF.")
    data = await file.read()
    if len(data) > MAX_PDF_BYTES:
        raise HTTPException(status_code=413, detail=f"Arquivo excede limite de {MAX_PDF_MB}MB.")
    repo = TaskRepository()
    repo.update_pdf(task_id, None if role == "admin" else scope_user_id, file.filename, data)

    TaskLogRepository().create(
        task_id=task_id,
        user_id=scope_user_id,
        action="upload_pdf",
        details=file.filename,
    )

    classification = classify_filename(file.filename)
    status = "ok" if classification.get("tributo") else "needs_review"
    classification["status"] = status
    classification["task_id"] = task_id
    classification["user_id"] = scope_user_id

    suggestions = []
    if status != "ok":
        task_row = repo.get(task_id, None if role == "admin" else scope_user_id)
        if task_row:
            suggestions = repo.find_similar(company_id=int(task_row["company_id"]), text=classification.get("raw_text") or "")

    json_path = save_classification_json(classification)
    class_repo = ClassificationRepository()
    class_repo.create(
        task_id=task_id,
        user_id=scope_user_id,
        filename=file.filename,
        competencia=classification.get("competencia"),
        empresa=classification.get("empresa") or "",
        grupo=classification.get("grupo"),
        subgrupo=classification.get("subgrupo"),
        orgao=classification.get("orgao"),
        tributo=classification.get("tributo"),
        subtipo=classification.get("subtipo"),
        acao=classification.get("acao"),
        confianca=classification.get("confianca") or 0,
        status=status,
        raw_text=classification.get("raw_text") or "",
    )

    task_row = repo.get(task_id, None if role == "admin" else scope_user_id)
    if task_row:
        company = CompanyRepository().get(int(task_row["company_id"]))
        text_pdf = _extract_pdf_text(data)
        issues = []
        if company and company.get("cnpj"):
            cnpj_pdf = _find_cnpj(text_pdf)
            cnpj_expected = _normalize_cnpj(company.get("cnpj") or "")
            if cnpj_pdf and cnpj_expected and cnpj_pdf != cnpj_expected:
                issues.append(f"CNPJ diferente (PDF {cnpj_pdf} != Empresa {cnpj_expected})")
        comp_expected = (task_row.get("competencia") or "").strip()
        comp_pdf = _find_competencia(text_pdf)
        if comp_expected and comp_pdf and comp_pdf != comp_expected:
            issues.append(f"Competência diferente (PDF {comp_pdf} != Tarefa {comp_expected})")
        trib_match = _match_tributo(text_pdf, task_row.get("tributo"))
        if trib_match is False:
            issues.append("Tributo não encontrado no PDF")
        if issues:
            TaskLogRepository().create(
                task_id=task_id,
                user_id=scope_user_id,
                action="inconsistency",
                details="; ".join(issues),
            )
            notify_user = task_row.get("user_id")
            if notify_user is not None:
                NotificationRepository().create(
                    user_id=int(notify_user),
                    type="inconsistency",
                    ref_id=task_id,
                    message=f"Inconsistência na tarefa {task_row.get('titulo')}: " + "; ".join(issues),
                )

    return {"ok": True, "classification": classification, "json_path": json_path, "suggestions": suggestions}


@app.get("/tasks/{task_id}/logs", response_model=List[TaskLogOut])
def list_task_logs(task_id: int, request: Request, user_id: Optional[int] = Query(None)):
    auth_user = request.state.auth_user
    scope_user_id = _resolve_query_user_id(auth_user, user_id)
    role = str(auth_user.get("role") or "collab")

    repo = TaskRepository()
    task = repo.get(task_id, None if _can_view_all(role) else scope_user_id)
    if not task:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada.")
    return TaskLogRepository().list(task_id=task_id)


@app.get("/tasks/{task_id}/comments", response_model=List[TaskCommentOut])
def list_task_comments(task_id: int, request: Request, user_id: Optional[int] = Query(None)):
    auth_user = request.state.auth_user
    scope_user_id = _resolve_query_user_id(auth_user, user_id)
    role = str(auth_user.get("role") or "collab")

    repo = TaskRepository()
    task = repo.get(task_id, None if _can_view_all(role) else scope_user_id)
    if not task:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada.")
    return TaskCommentRepository().list(task_id=task_id)


@app.post("/tasks/{task_id}/comments", response_model=TaskCommentOut)
def create_task_comment(task_id: int, payload: TaskCommentCreate, request: Request, user_id: Optional[int] = Query(None)):
    auth_user = request.state.auth_user
    scope_user_id = _resolve_query_user_id(auth_user, user_id)
    role = str(auth_user.get("role") or "collab")

    if role not in {"admin", "manager"}:
        raise HTTPException(status_code=403, detail="Sem permissão para comentar.")

    repo = TaskRepository()
    task = repo.get(task_id, None if _can_view_all(role) else scope_user_id)
    if not task:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada.")

    comment_repo = TaskCommentRepository()
    new_id = comment_repo.create(task_id=task_id, author_id=scope_user_id, text=payload.text)

    NotificationRepository().create(
        user_id=int(task.get("user_id")),
        type="comment",
        ref_id=int(task_id),
        message=f"Novo comentário na tarefa {task.get('titulo')} (id {task_id})",
    )

    created = comment_repo.get(new_id)
    return created or {
        "id": new_id,
        "task_id": task_id,
        "author_id": scope_user_id,
        "text": payload.text,
        "created_at": "",
    }


@app.post("/tasks/{task_id}/comments/{comment_id}/ack")
def acknowledge_task_comment(task_id: int, comment_id: int, request: Request, user_id: Optional[int] = Query(None)):
    auth_user = request.state.auth_user
    scope_user_id = _resolve_query_user_id(auth_user, user_id)
    role = str(auth_user.get("role") or "collab")

    if role not in {"admin", "collab"}:
        raise HTTPException(status_code=403, detail="Apenas administrador/colaborador podem confirmar.")

    task_repo = TaskRepository()
    task = task_repo.get(task_id, None if _can_view_all(role) else scope_user_id)
    if not task:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada.")

    comment_repo = TaskCommentRepository()
    comment = comment_repo.get(comment_id)
    if not comment or int(comment.get("task_id") or 0) != int(task_id):
        raise HTTPException(status_code=404, detail="Comentário não encontrado.")

    if _get_role(int(comment.get("author_id") or 0)) != "manager":
        raise HTTPException(status_code=400, detail="Somente comentário de coordenador pode ser confirmado.")

    users = UserRepository().list()
    actor_name = next((str(u.get("nome") or "") for u in users if int(u.get("id") or 0) == int(scope_user_id)), f"Usuário {scope_user_id}")

    notif_repo = NotificationRepository()
    notif_repo.create(
        user_id=int(comment["author_id"]),
        type="resolved",
        ref_id=int(task_id),
        message=f"{actor_name} conferiu seu comentário na tarefa {task.get('titulo')} (id {task_id})",
    )

    TaskLogRepository().create(
        task_id=task_id,
        user_id=scope_user_id,
        action="comment_ack",
        details=f"comment_id={comment_id}",
    )
    return {"ok": True}


@app.get("/notifications", response_model=List[NotificationOut])
def list_notifications(request: Request, user_id: Optional[int] = Query(None), unread_only: bool = False):
    auth_user = request.state.auth_user
    scope_user_id = _resolve_query_user_id(auth_user, user_id)

    repo = NotificationRepository()
    rows = repo.list(user_id=scope_user_id, unread_only=unread_only)
    return [
        {
            **r,
            "is_read": bool(r.get("is_read")),
        }
        for r in rows
    ]


@app.patch("/notifications/{notification_id}/read")
def mark_notification_read(notification_id: int, request: Request, user_id: Optional[int] = Query(None)):
    auth_user = request.state.auth_user
    scope_user_id = _resolve_query_user_id(auth_user, user_id)

    repo = NotificationRepository()
    repo.mark_read(notification_id, scope_user_id)
    return {"ok": True}


@app.get("/tasks/{task_id}/pdf")
def download_pdf(task_id: int, request: Request, user_id: Optional[int] = Query(None)):
    auth_user = request.state.auth_user
    scope_user_id = _resolve_query_user_id(auth_user, user_id)
    role = str(auth_user.get("role") or "collab")

    repo = TaskRepository()
    row = repo.get_pdf(task_id, None if _can_view_all(role) else scope_user_id)
    if not row or not row.get("pdf_blob"):
        raise HTTPException(status_code=404, detail="PDF não encontrado.")

    data = row["pdf_blob"]
    filename = row.get("pdf_path") or f"task_{task_id}.pdf"
    return StreamingResponse(
        iter([data]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )
