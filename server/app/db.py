from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Optional


def _default_data_dir() -> Path:
    if os.name == "nt":
        base = os.environ.get("APPDATA") or str(Path.home())
        return Path(base) / "notion_like_app"
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / "notion_like_app"


def get_db_path() -> str:
    override = os.environ.get("FISCAL_DB_PATH")
    if override:
        return override
    data_dir = _default_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    return str(data_dir / "app.db")


def get_data_dir() -> Path:
    data_dir = _default_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


DB_PATH = get_db_path()


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys=ON")
    except Exception:
        pass
    return conn


def init_db() -> None:
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL UNIQUE,
            role TEXT NOT NULL DEFAULT 'collab',
            is_default INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    # Migração leve para colunas novas
    cols = [r[1] for r in cur.execute("PRAGMA table_info(usuarios);").fetchall()]
    if "senha" not in cols:
        cur.execute("ALTER TABLE usuarios ADD COLUMN senha TEXT NOT NULL DEFAULT '1234'")
    if "role" not in cols:
        cur.execute("ALTER TABLE usuarios ADD COLUMN role TEXT NOT NULL DEFAULT 'collab'")
    if "is_default" not in cols:
        cur.execute("ALTER TABLE usuarios ADD COLUMN is_default INTEGER NOT NULL DEFAULT 0")
    # garante senha padrao para registros antigos
    cur.execute("UPDATE usuarios SET senha = '1234' WHERE senha IS NULL OR senha = ''")
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS empresas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            nome TEXT NOT NULL,
            cnpj TEXT,
            ie TEXT,
            regime TEXT,
            observacoes TEXT,
            FOREIGN KEY(user_id) REFERENCES usuarios(id)
        )
        """
    )
    cols_emp = [r[1] for r in cur.execute("PRAGMA table_info(empresas);").fetchall()]
    if "observacoes" not in cols_emp:
        cur.execute("ALTER TABLE empresas ADD COLUMN observacoes TEXT")
    if "data_entrada" not in cols_emp:
        cur.execute("ALTER TABLE empresas ADD COLUMN data_entrada TEXT")
    if "data_saida" not in cols_emp:
        cur.execute("ALTER TABLE empresas ADD COLUMN data_saida TEXT")
    if "responsavel_id" not in cols_emp:
        cur.execute("ALTER TABLE empresas ADD COLUMN responsavel_id INTEGER")
        cur.execute("UPDATE empresas SET responsavel_id = user_id WHERE responsavel_id IS NULL")
    if "email_principal" not in cols_emp:
        cur.execute("ALTER TABLE empresas ADD COLUMN email_principal TEXT")
    if "emails_extra" not in cols_emp:
        cur.execute("ALTER TABLE empresas ADD COLUMN emails_extra TEXT")
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS tarefas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            company_id INTEGER NOT NULL,
            titulo TEXT NOT NULL,
            tipo TEXT NOT NULL,
            orgao TEXT NOT NULL,
            tributo TEXT,
            competencia TEXT,
            vencimento TEXT,
            status TEXT NOT NULL,
            pdf_path TEXT,
            pdf_blob BLOB,
            FOREIGN KEY(company_id) REFERENCES empresas(id),
            FOREIGN KEY(user_id) REFERENCES usuarios(id)
        )
        """
    )
    cols_task = [r[1] for r in cur.execute("PRAGMA table_info(tarefas);").fetchall()]
    if "vencimento" not in cols_task:
        cur.execute("ALTER TABLE tarefas ADD COLUMN vencimento TEXT")
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS task_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            user_id INTEGER,
            action TEXT NOT NULL,
            details TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY(task_id) REFERENCES tarefas(id),
            FOREIGN KEY(user_id) REFERENCES usuarios(id)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS email_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            to_emails TEXT NOT NULL,
            subject TEXT,
            body TEXT,
            link TEXT,
            task_id INTEGER,
            attachment_name TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY(company_id) REFERENCES empresas(id),
            FOREIGN KEY(user_id) REFERENCES usuarios(id),
            FOREIGN KEY(task_id) REFERENCES tarefas(id)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS task_comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            author_id INTEGER NOT NULL,
            text TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY(task_id) REFERENCES tarefas(id),
            FOREIGN KEY(author_id) REFERENCES usuarios(id)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            type TEXT NOT NULL,
            ref_id INTEGER,
            message TEXT NOT NULL,
            is_read INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY(user_id) REFERENCES usuarios(id)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS classificacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER,
            user_id INTEGER,
            filename TEXT,
            competencia TEXT,
            empresa TEXT,
            grupo TEXT,
            subgrupo TEXT,
            orgao TEXT,
            tributo TEXT,
            subtipo TEXT,
            acao TEXT,
            confianca REAL,
            status TEXT,
            raw_text TEXT,
            created_at TEXT,
            FOREIGN KEY(task_id) REFERENCES tarefas(id),
            FOREIGN KEY(user_id) REFERENCES usuarios(id)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    cols_cls = [r[1] for r in cur.execute("PRAGMA table_info(classificacoes);").fetchall()]
    if "subgrupo" not in cols_cls:
        cur.execute("ALTER TABLE classificacoes ADD COLUMN subgrupo TEXT")
    conn.commit()
    conn.close()
