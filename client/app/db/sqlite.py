from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import List, Dict, Optional, Any


def _default_data_dir() -> Path:
    """Retorna um diretório gravável por usuário para armazenar dados locais."""
    if os.name == "nt":
        base = os.environ.get("APPDATA") or str(Path.home())
        return Path(base) / "notion_like_app"
    # Linux/macOS: respeita XDG se existir
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / "notion_like_app"


def get_db_path() -> str:
    """Permite override via env var, e por padrão usa AppData do usuário."""
    override = os.environ.get("NOTION_LIKE_DB_PATH")
    if override:
        return override

    data_dir = _default_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    return str(data_dir / "app.db")


DB_PATH = get_db_path()


def get_data_dir() -> Path:
    """Diretório base de dados do app (por usuário)."""
    p = _default_data_dir()
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_attachments_dir() -> Path:
    """Pasta interna para anexos (1 PDF por tarefa)."""
    p = get_data_dir() / "attachments"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # Garante integridade referencial quando FK existir
    try:
        conn.execute("PRAGMA foreign_keys=ON")
    except Exception:
        pass
    return conn


def _ensure_tarefas_pdf_column(cur) -> None:
    """Migração segura: adiciona coluna pdf_path se ainda não existir."""
    cols = [r[1] for r in cur.execute("PRAGMA table_info(tarefas);").fetchall()]
    if "pdf_path" not in cols:
        cur.execute("ALTER TABLE tarefas ADD COLUMN pdf_path TEXT;")


def _ensure_tarefas_pdf_blob_column(cur) -> None:
    """Migração segura: adiciona coluna pdf_blob se ainda não existir."""
    cols = [r[1] for r in cur.execute("PRAGMA table_info(tarefas);").fetchall()]
    if "pdf_blob" not in cols:
        cur.execute("ALTER TABLE tarefas ADD COLUMN pdf_blob BLOB;")


def _ensure_empresas_user_column(cur) -> None:
    cols = [r[1] for r in cur.execute("PRAGMA table_info(empresas);").fetchall()]
    if "user_id" not in cols:
        cur.execute("ALTER TABLE empresas ADD COLUMN user_id INTEGER;")


def _ensure_tarefas_user_column(cur) -> None:
    cols = [r[1] for r in cur.execute("PRAGMA table_info(tarefas);").fetchall()]
    if "user_id" not in cols:
        cur.execute("ALTER TABLE tarefas ADD COLUMN user_id INTEGER;")


def _ensure_users_table(cur) -> None:
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL UNIQUE
        )
        """
    )


def _ensure_default_user(cur) -> int:
    _ensure_users_table(cur)
    row = cur.execute("SELECT id FROM usuarios ORDER BY id LIMIT 1").fetchone()
    if row:
        return int(row[0])
    cur.execute("INSERT INTO usuarios (nome) VALUES (?)", ("Admin",))
    return int(cur.lastrowid)


def _normalize_pdf_paths(cur) -> None:
    """Converte pdf_path absoluto para apenas o nome do arquivo (quando for anexo interno)."""
    try:
        base = str(get_attachments_dir().resolve())
    except Exception:
        return
    rows = cur.execute(
        "SELECT id, pdf_path FROM tarefas WHERE pdf_path IS NOT NULL AND pdf_path != ''"
    ).fetchall()
    for r in rows:
        task_id = r[0]
        raw = r[1]
        if not raw:
            continue
        try:
            raw_s = str(raw)
            if raw_s.startswith("\\") and not raw_s.startswith("\\\\"):
                drive = os.environ.get("SystemDrive") or "C:"
                raw_s = f"{drive}{raw_s}"
            p = Path(raw_s)
            if not p.is_absolute():
                continue
            target = str(p.resolve())
            import os
            if p.suffix.lower() != ".pdf":
                continue
            if os.path.commonpath([base, target]) == base:
                cur.execute(
                    "UPDATE tarefas SET pdf_path = ? WHERE id = ?",
                    (p.name, int(task_id)),
                )
        except Exception:
            continue


def init_db():
    conn = _connect()
    cur = conn.cursor()
    default_user_id = _ensure_default_user(cur)
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS empresas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            nome TEXT NOT NULL,
            cnpj TEXT,
            ie TEXT,
            regime TEXT,
            FOREIGN KEY(user_id) REFERENCES usuarios(id)
        )
        """
    )

    # Tarefas (Obrigações / Acessórias)
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS tarefas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            company_id INTEGER NOT NULL,
            titulo TEXT NOT NULL,
            tipo TEXT NOT NULL,          -- OBR | ACS
            orgao TEXT NOT NULL,         -- MUN | EST | FED
            tributo TEXT,
            competencia TEXT,            -- YYYYMM
            status TEXT NOT NULL,
            pdf_path TEXT,
            pdf_blob BLOB,
            FOREIGN KEY(company_id) REFERENCES empresas(id),
            FOREIGN KEY(user_id) REFERENCES usuarios(id)
        )
        """
    )

    # Compatibilidade com banco existente (não recriar / não perder dados)
    _ensure_empresas_user_column(cur)
    _ensure_tarefas_user_column(cur)
    _ensure_tarefas_pdf_column(cur)
    _ensure_tarefas_pdf_blob_column(cur)
    _normalize_pdf_paths(cur)
    cur.execute(
        "UPDATE empresas SET user_id = ? WHERE user_id IS NULL",
        (int(default_user_id),),
    )
    cur.execute(
        "UPDATE tarefas SET user_id = ? WHERE user_id IS NULL",
        (int(default_user_id),),
    )
    conn.commit()

    # Seed mínimo para não abrir a Home vazia na 1ª execução.
    count = cur.execute("SELECT COUNT(1) FROM empresas").fetchone()[0]
    if int(count) == 0:
        cur.executemany(
            "INSERT INTO empresas (user_id, nome, cnpj, ie, regime) VALUES (?, ?, ?, ?, ?)",
            [
                (default_user_id, "ALL METAL LTDA", "00.000.000/0001-00", "ISENTO", "Simples Nacional"),
                (default_user_id, "EXEMPLO TRANSPORTES", "11.111.111/0001-11", "123456", "Lucro Presumido"),
            ],
        )
        conn.commit()

    # Seed de tarefas (apenas se a tabela estiver vazia)
    tcount = cur.execute("SELECT COUNT(1) FROM tarefas").fetchone()[0]
    if int(tcount) == 0:
        # Usa as 2 primeiras empresas como exemplo (se existirem)
        ids = [r[0] for r in cur.execute("SELECT id FROM empresas ORDER BY id LIMIT 2").fetchall()]
        if not ids:
            ids = [1]
        cid1 = ids[0]
        cid2 = ids[1] if len(ids) > 1 else ids[0]

        cur.executemany(
            """
            INSERT INTO tarefas (user_id, company_id, titulo, tipo, orgao, tributo, competencia, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (default_user_id, cid1, "ISS TOMADOS", "OBR", "MUN", "ISS", "202602", "PENDENTE"),
                (default_user_id, cid1, "ICMS", "OBR", "EST", "ICMS", "202602", "EM_ANDAMENTO"),
                (default_user_id, cid1, "EFD REINF", "ACS", "FED", "SPED", "202602", "CONCLUIDA"),
                (default_user_id, cid1, "DARF IRPJ", "OBR", "FED", "IRPJ", "202602", "ENVIADA"),
                (default_user_id, cid2, "EFD FISCAL", "ACS", "EST", "SPED", "202601", "PENDENTE"),
                (default_user_id, cid2, "GIA", "ACS", "EST", "ICMS", "202601", "PENDENTE"),
            ],
        )
        conn.commit()
    conn.close()


def empresas_list(*, query: str = "", regime: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Lista empresas. Compatível com chamadas antigas:
    - empresas_list()
    - empresas_list(query="abc")
    - empresas_list(regime="Simples Nacional")
    """
    conn = _connect()
    cur = conn.cursor()

    q = "SELECT id, nome, cnpj, ie, regime FROM empresas WHERE 1=1"
    params: list[Any] = []

    if regime and regime != "Todas":
        q += " AND regime = ?"
        params.append(regime)

    s = (query or "").strip()
    if s:
        q += " AND (nome LIKE ? OR cnpj LIKE ?)"
        like = f"%{s}%"
        params.extend([like, like])

    q += " ORDER BY nome COLLATE NOCASE"
    rows = cur.execute(q, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def empresa_get(company_id: int) -> Optional[Dict[str, Any]]:
    conn = _connect()
    cur = conn.cursor()
    row = cur.execute(
        "SELECT id, nome, cnpj, ie, regime FROM empresas WHERE id = ?",
        (int(company_id),),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def empresa_update(company_id: int, *, cnpj: str, ie: str, regime: str) -> None:
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "UPDATE empresas SET cnpj = ?, ie = ?, regime = ? WHERE id = ?",
        (cnpj, ie, regime, int(company_id)),
    )
    conn.commit()
    conn.close()
