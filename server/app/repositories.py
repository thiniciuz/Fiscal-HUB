from __future__ import annotations

from typing import List, Optional, Dict
import json

from .db import _connect
from .security import hash_password, is_password_hash, verify_password


class UserRepository:
    def list(self) -> List[Dict[str, object]]:
        conn = _connect()
        cur = conn.cursor()
        rows = cur.execute(
            "SELECT id, nome, role, is_default, senha FROM usuarios ORDER BY nome COLLATE NOCASE"
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def create(self, nome: str, role: str = "collab", is_default: bool = False, senha: str = "1234") -> int:
        nome = (nome or "").strip()
        if not nome:
            raise ValueError("Nome do usuário é obrigatório")
        conn = _connect()
        cur = conn.cursor()
        if is_default:
            cur.execute("UPDATE usuarios SET is_default = 0")
        cur.execute(
            "INSERT INTO usuarios (nome, role, is_default, senha) VALUES (?, ?, ?, ?)",
            (nome, role, 1 if is_default else 0, hash_password(senha)),
        )
        conn.commit()
        new_id = int(cur.lastrowid)
        conn.close()
        return new_id

    def get_by_nome(self, nome: str) -> Optional[Dict[str, object]]:
        conn = _connect()
        cur = conn.cursor()
        row = cur.execute(
            "SELECT id, nome, role, is_default, senha FROM usuarios WHERE nome = ?",
            ((nome or "").strip(),),
        ).fetchone()
        conn.close()
        return dict(row) if row else None

    def set_default(self, user_id: int) -> None:
        conn = _connect()
        cur = conn.cursor()
        cur.execute("UPDATE usuarios SET is_default = 0")
        cur.execute("UPDATE usuarios SET is_default = 1 WHERE id = ?", (int(user_id),))
        conn.commit()
        conn.close()

    def update_role(self, user_id: int, role: str) -> None:
        conn = _connect()
        cur = conn.cursor()
        cur.execute("UPDATE usuarios SET role = ? WHERE id = ?", (role, int(user_id)))
        conn.commit()
        conn.close()

    def verify_login(self, nome: str, senha: str) -> Optional[Dict[str, object]]:
        conn = _connect()
        cur = conn.cursor()
        row = cur.execute(
            "SELECT id, nome, role, is_default, senha FROM usuarios WHERE nome = ?",
            ((nome or "").strip(),),
        ).fetchone()
        if not row:
            conn.close()
            return None

        out = dict(row)
        stored = str(out.get("senha") or "")
        if not verify_password(senha, stored):
            conn.close()
            return None

        # Migração transparente para hash forte em logins de contas antigas.
        if not is_password_hash(stored):
            cur.execute(
                "UPDATE usuarios SET senha = ? WHERE id = ?",
                (hash_password(senha), int(out["id"])),
            )
            conn.commit()

        conn.close()
        return out

    def migrate_plaintext_passwords(self) -> int:
        conn = _connect()
        cur = conn.cursor()
        rows = cur.execute("SELECT id, senha FROM usuarios").fetchall()
        changed = 0
        for row in rows:
            user_id = int(row["id"])
            stored = str(row["senha"] or "").strip() or "1234"
            if is_password_hash(stored):
                continue
            cur.execute(
                "UPDATE usuarios SET senha = ? WHERE id = ?",
                (hash_password(stored), user_id),
            )
            changed += 1
        conn.commit()
        conn.close()
        return changed


class CompanyRepository:
    def _normalize_observacoes_out(self, value: Optional[str]) -> List[str]:
        if value is None:
            return []
        raw = str(value).strip()
        if not raw:
            return []
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [str(x) for x in parsed if str(x).strip()]
        except Exception:
            pass
        return [raw]

    def _normalize_observacoes_in(self, value: object) -> str:
        if value is None:
            return ""
        if isinstance(value, list):
            cleaned = [str(x).strip() for x in value if str(x).strip()]
            return json.dumps(cleaned, ensure_ascii=False)
        return str(value).strip()

    def _normalize_emails_out(self, value: Optional[str]) -> List[str]:
        if value is None:
            return []
        raw = str(value).strip()
        if not raw:
            return []
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [str(x) for x in parsed if str(x).strip()]
        except Exception:
            pass
        parts = [p.strip() for p in raw.replace(";", ",").split(",")]
        return [p for p in parts if p]

    def _normalize_emails_in(self, value: object) -> str:
        if value is None:
            return ""
        if isinstance(value, list):
            cleaned = [str(x).strip() for x in value if str(x).strip()]
            return json.dumps(cleaned, ensure_ascii=False)
        return str(value).strip()

    def _parse_competencia(self, competencia: str) -> Optional[str]:
        s = (competencia or "").strip()
        if not s:
            return None
        if len(s) == 6 and s.isdigit():
            return f"{s[:4]}-{s[4:6]}-01"
        if len(s) == 7 and s[2] == "/":
            mm, yyyy = s.split("/")
            if mm.isdigit() and yyyy.isdigit():
                return f"{yyyy}-{mm.zfill(2)}-01"
        if len(s) == 10 and s[4] == "-" and s[7] == "-":
            return s
        return None

    def list(
        self,
        user_id: Optional[int],
        *,
        responsavel_id: Optional[int] = None,
        query: str = "",
        regime: Optional[str] = None,
        competencia: Optional[str] = None,
    ) -> List[Dict[str, object]]:
        conn = _connect()
        cur = conn.cursor()
        q = (
            "SELECT id, nome, cnpj, ie, regime, observacoes, data_entrada, data_saida, responsavel_id, email_principal, emails_extra "
            "FROM empresas WHERE 1=1"
        )
        params: list[object] = []
        if user_id is not None:
            q += " AND user_id = ?"
            params.append(int(user_id))
        if responsavel_id is not None:
            q += " AND responsavel_id = ?"
            params.append(int(responsavel_id))
        if regime and regime != "Todas":
            q += " AND TRIM(regime) = TRIM(?) COLLATE NOCASE"
            params.append(regime)
        comp_date = self._parse_competencia(competencia or "")
        if comp_date:
            q += " AND (data_entrada IS NULL OR data_entrada <= ?)"
            params.append(comp_date)
            q += " AND (data_saida IS NULL OR data_saida >= ?)"
            params.append(comp_date)
        s = (query or "").strip()
        if s:
            q += " AND (nome LIKE ? OR cnpj LIKE ?)"
            like = f"%{s}%"
            params.extend([like, like])
        q += " ORDER BY nome COLLATE NOCASE"
        rows = cur.execute(q, params).fetchall()
        conn.close()
        out = []
        for r in rows:
            d = dict(r)
            d["observacoes"] = self._normalize_observacoes_out(d.get("observacoes"))
            d["email_principal"] = (d.get("email_principal") or "").strip()
            d["emails_extra"] = self._normalize_emails_out(d.get("emails_extra"))
            out.append(d)
        return out

    def get(self, company_id: int) -> Optional[Dict[str, object]]:
        conn = _connect()
        cur = conn.cursor()
        row = cur.execute(
            """
            SELECT id, nome, cnpj, ie, regime, observacoes, data_entrada, data_saida, responsavel_id, email_principal, emails_extra
            FROM empresas WHERE id = ?
            """,
            (int(company_id),),
        ).fetchone()
        conn.close()
        if not row:
            return None
        d = dict(row)
        d["observacoes"] = self._normalize_observacoes_out(d.get("observacoes"))
        d["email_principal"] = (d.get("email_principal") or "").strip()
        d["emails_extra"] = self._normalize_emails_out(d.get("emails_extra"))
        return d

    def create(
        self,
        *,
        user_id: int,
        nome: str,
        cnpj: str = "",
        ie: str = "",
        regime: str = "",
        observacoes: str = "",
        data_entrada: Optional[str] = None,
        data_saida: Optional[str] = None,
        responsavel_id: Optional[int] = None,
        email_principal: str = "",
        emails_extra: object = "",
    ) -> int:
        nome = (nome or "").strip()
        if not nome:
            raise ValueError("Nome da empresa é obrigatório")
        conn = _connect()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO empresas (
                user_id, nome, cnpj, ie, regime, observacoes, data_entrada, data_saida, responsavel_id, email_principal, emails_extra
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(user_id),
                nome,
                (cnpj or "").strip(),
                (ie or "").strip(),
                (regime or "").strip(),
                self._normalize_observacoes_in(observacoes),
                (data_entrada or "").strip() if data_entrada else None,
                (data_saida or "").strip() if data_saida else None,
                int(responsavel_id) if responsavel_id is not None else None,
                    (email_principal or "").strip(),
                    self._normalize_emails_in(emails_extra),
            ),
        )
        conn.commit()
        new_id = int(cur.lastrowid)
        conn.close()
        return new_id

    def update(
        self,
        *,
        user_id: Optional[int],
        company_id: int,
        nome: str,
        cnpj: str = "",
        ie: str = "",
        regime: str = "",
        observacoes: str = "",
        data_entrada: Optional[str] = None,
        data_saida: Optional[str] = None,
        responsavel_id: Optional[int] = None,
        email_principal: str = "",
        emails_extra: object = "",
    ) -> None:
        conn = _connect()
        cur = conn.cursor()
        if user_id is None:
            cur.execute(
                """
                UPDATE empresas
                SET nome = ?, cnpj = ?, ie = ?, regime = ?, observacoes = ?, data_entrada = ?, data_saida = ?, responsavel_id = ?,
                    email_principal = ?, emails_extra = ?
                WHERE id = ?
                """,
                (
                    (nome or "").strip(),
                    (cnpj or "").strip(),
                    (ie or "").strip(),
                    (regime or "").strip(),
                    self._normalize_observacoes_in(observacoes),
                    (data_entrada or "").strip() if data_entrada else None,
                    (data_saida or "").strip() if data_saida else None,
                    int(responsavel_id) if responsavel_id is not None else None,
                    (email_principal or "").strip(),
                    self._normalize_emails_in(emails_extra),
                    int(company_id),
                ),
            )
        else:
            cur.execute(
                """
                UPDATE empresas
                SET nome = ?, cnpj = ?, ie = ?, regime = ?, observacoes = ?, data_entrada = ?, data_saida = ?, responsavel_id = ?,
                    email_principal = ?, emails_extra = ?
                WHERE id = ? AND user_id = ?
                """,
                (
                    (nome or "").strip(),
                    (cnpj or "").strip(),
                    (ie or "").strip(),
                    (regime or "").strip(),
                    self._normalize_observacoes_in(observacoes),
                    (data_entrada or "").strip() if data_entrada else None,
                    (data_saida or "").strip() if data_saida else None,
                    int(responsavel_id) if responsavel_id is not None else None,
                    (email_principal or "").strip(),
                    self._normalize_emails_in(emails_extra),
                    int(company_id),
                    int(user_id),
                ),
            )
        conn.commit()
        conn.close()

    def update_responsavel(self, company_id: int, responsavel_id: int) -> None:
        conn = _connect()
        cur = conn.cursor()
        cur.execute(
            "UPDATE empresas SET responsavel_id = ? WHERE id = ?",
            (int(responsavel_id), int(company_id)),
        )
        conn.commit()
        conn.close()


class TaskRepository:
    def list(
        self,
        *,
        user_id: Optional[int],
        company_id: Optional[int] = None,
        status: Optional[List[str]] = None,
        tipo: Optional[str] = None,
        competencia: Optional[str] = None,
    ) -> List[Dict[str, object]]:
        conn = _connect()
        cur = conn.cursor()
        q = (
            "SELECT id, company_id, titulo, tipo, orgao, tributo, competencia, vencimento, status, pdf_path, "
            "CASE WHEN pdf_blob IS NOT NULL THEN 1 ELSE 0 END as has_pdf "
            "FROM tarefas WHERE 1=1"
        )
        params: list[object] = []
        if user_id is not None:
            q += " AND user_id = ?"
            params.append(int(user_id))
        if company_id is not None:
            q += " AND company_id = ?"
            params.append(int(company_id))
        if status:
            placeholders = ",".join("?" for _ in status)
            q += f" AND status IN ({placeholders})"
            params.extend([str(s) for s in status])
        if tipo:
            q += " AND tipo = ?"
            params.append(str(tipo))
        if competencia:
            q += " AND competencia = ?"
            params.append(str(competencia))
        q += " ORDER BY competencia DESC, titulo COLLATE NOCASE"
        rows = cur.execute(q, params).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def list_upcoming(
        self,
        *,
        user_id: Optional[int],
        days: int = 7,
        competencia: Optional[str] = None,
    ) -> List[Dict[str, object]]:
        conn = _connect()
        cur = conn.cursor()
        q = (
            "SELECT id, company_id, titulo, tipo, orgao, tributo, competencia, vencimento, status, pdf_path, "
            "CASE WHEN pdf_blob IS NOT NULL THEN 1 ELSE 0 END as has_pdf "
            "FROM tarefas WHERE vencimento IS NOT NULL AND TRIM(vencimento) <> '' "
            "AND date(vencimento) >= date('now') AND date(vencimento) <= date('now', ?)"
        )
        params: list[object] = [f"+{int(days)} day"]
        if user_id is not None:
            q += " AND user_id = ?"
            params.append(int(user_id))
        if competencia:
            q += " AND competencia = ?"
            params.append(str(competencia))
        q += " ORDER BY date(vencimento) ASC, titulo COLLATE NOCASE"
        rows = cur.execute(q, params).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def create(
        self,
        *,
        user_id: int,
        company_id: int,
        titulo: str,
        tipo: str,
        orgao: str,
        tributo: str = "",
        competencia: Optional[str] = None,
        vencimento: Optional[str] = None,
        status: str,
    ) -> int:
        conn = _connect()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO tarefas (user_id, company_id, titulo, tipo, orgao, tributo, competencia, vencimento, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(user_id),
                int(company_id),
                titulo,
                tipo,
                orgao,
                (tributo or "").strip(),
                (competencia or "").strip() if competencia else None,
                (vencimento or "").strip() if vencimento else None,
                status,
            ),
        )
        conn.commit()
        new_id = int(cur.lastrowid)
        conn.close()
        return new_id

    def update_status(self, task_id: int, user_id: Optional[int], new_status: str) -> None:
        conn = _connect()
        cur = conn.cursor()
        if user_id is None:
            cur.execute(
                "UPDATE tarefas SET status = ? WHERE id = ?",
                (str(new_status), int(task_id)),
            )
        else:
            cur.execute(
                "UPDATE tarefas SET status = ? WHERE id = ? AND user_id = ?",
                (str(new_status), int(task_id), int(user_id)),
            )
        conn.commit()
        conn.close()

    def update(
        self,
        *,
        task_id: int,
        user_id: Optional[int],
        titulo: str,
        tipo: str,
        orgao: str,
        tributo: str = "",
        competencia: Optional[str] = None,
        vencimento: Optional[str] = None,
        status: str,
    ) -> None:
        conn = _connect()
        cur = conn.cursor()
        if user_id is None:
            cur.execute(
                """
                UPDATE tarefas
                SET titulo = ?, tipo = ?, orgao = ?, tributo = ?, competencia = ?, vencimento = ?, status = ?
                WHERE id = ?
                """,
                (
                    (titulo or "").strip(),
                    str(tipo),
                    str(orgao),
                    (tributo or "").strip(),
                    (competencia or "").strip() if competencia else None,
                    (vencimento or "").strip() if vencimento else None,
                    str(status),
                    int(task_id),
                ),
            )
        else:
            cur.execute(
                """
                UPDATE tarefas
                SET titulo = ?, tipo = ?, orgao = ?, tributo = ?, competencia = ?, vencimento = ?, status = ?
                WHERE id = ? AND user_id = ?
                """,
                (
                    (titulo or "").strip(),
                    str(tipo),
                    str(orgao),
                    (tributo or "").strip(),
                    (competencia or "").strip() if competencia else None,
                    (vencimento or "").strip() if vencimento else None,
                    str(status),
                    int(task_id),
                    int(user_id),
                ),
            )
        conn.commit()
        conn.close()

    def get_pdf(self, task_id: int, user_id: Optional[int]) -> Optional[Dict[str, object]]:
        conn = _connect()
        cur = conn.cursor()
        if user_id is None:
            row = cur.execute(
                "SELECT pdf_path, pdf_blob FROM tarefas WHERE id = ?",
                (int(task_id),),
            ).fetchone()
        else:
            row = cur.execute(
                "SELECT pdf_path, pdf_blob FROM tarefas WHERE id = ? AND user_id = ?",
                (int(task_id), int(user_id)),
            ).fetchone()
        conn.close()
        return dict(row) if row else None

    def get(self, task_id: int, user_id: Optional[int]) -> Optional[Dict[str, object]]:
        conn = _connect()
        cur = conn.cursor()
        if user_id is None:
            row = cur.execute(
                """
                SELECT id, user_id, company_id, titulo, tipo, orgao, tributo, competencia, vencimento, status, pdf_path,
                CASE WHEN pdf_blob IS NOT NULL THEN 1 ELSE 0 END as has_pdf
                FROM tarefas WHERE id = ?
                """,
                (int(task_id),),
            ).fetchone()
        else:
            row = cur.execute(
                """
                SELECT id, user_id, company_id, titulo, tipo, orgao, tributo, competencia, vencimento, status, pdf_path,
                CASE WHEN pdf_blob IS NOT NULL THEN 1 ELSE 0 END as has_pdf
                FROM tarefas WHERE id = ? AND user_id = ?
                """,
                (int(task_id), int(user_id)),
            ).fetchone()
        conn.close()
        return dict(row) if row else None

    def update_pdf(self, task_id: int, user_id: Optional[int], pdf_path: str, pdf_blob: bytes) -> None:
        conn = _connect()
        cur = conn.cursor()
        if user_id is None:
            cur.execute(
                "UPDATE tarefas SET pdf_path = ?, pdf_blob = ? WHERE id = ?",
                (pdf_path, pdf_blob, int(task_id)),
            )
        else:
            cur.execute(
                "UPDATE tarefas SET pdf_path = ?, pdf_blob = ? WHERE id = ? AND user_id = ?",
                (pdf_path, pdf_blob, int(task_id), int(user_id)),
            )
        conn.commit()
        conn.close()


class TaskLogRepository:
    def create(self, *, task_id: int, user_id: Optional[int], action: str, details: Optional[str] = None) -> int:
        conn = _connect()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO task_logs (task_id, user_id, action, details)
            VALUES (?, ?, ?, ?)
            """,
            (
                int(task_id),
                int(user_id) if user_id is not None else None,
                (action or "").strip(),
                (details or "").strip() if details else None,
            ),
        )
        conn.commit()
        new_id = int(cur.lastrowid)
        conn.close()
        return new_id

    def list(self, *, task_id: int) -> List[Dict[str, object]]:
        conn = _connect()
        cur = conn.cursor()
        rows = cur.execute(
            """
            SELECT id, task_id, user_id, action, details, created_at
            FROM task_logs
            WHERE task_id = ?
            ORDER BY id DESC
            """,
            (int(task_id),),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]


class TaskCommentRepository:
    def list(self, *, task_id: int) -> List[Dict[str, object]]:
        conn = _connect()
        cur = conn.cursor()
        rows = cur.execute(
            """
            SELECT id, task_id, author_id, text, created_at
            FROM task_comments
            WHERE task_id = ?
            ORDER BY id DESC
            """,
            (int(task_id),),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def create(self, *, task_id: int, author_id: int, text: str) -> int:
        conn = _connect()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO task_comments (task_id, author_id, text)
            VALUES (?, ?, ?)
            """,
            (int(task_id), int(author_id), (text or "").strip()),
        )
        conn.commit()
        new_id = int(cur.lastrowid)
        conn.close()
        return new_id

    def get(self, comment_id: int) -> Optional[Dict[str, object]]:
        conn = _connect()
        cur = conn.cursor()
        row = cur.execute(
            """
            SELECT id, task_id, author_id, text, created_at
            FROM task_comments WHERE id = ?
            """,
            (int(comment_id),),
        ).fetchone()
        conn.close()
        return dict(row) if row else None


class NotificationRepository:
    def list(self, *, user_id: int, unread_only: bool = False) -> List[Dict[str, object]]:
        conn = _connect()
        cur = conn.cursor()
        q = (
            "SELECT id, user_id, type, ref_id, message, is_read, created_at "
            "FROM notifications WHERE user_id = ?"
        )
        params: list[object] = [int(user_id)]
        if unread_only:
            q += " AND is_read = 0"
        q += " ORDER BY id DESC"
        rows = cur.execute(q, params).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def create(
        self, *, user_id: int, type: str, ref_id: Optional[int], message: str
    ) -> int:
        conn = _connect()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO notifications (user_id, type, ref_id, message)
            VALUES (?, ?, ?, ?)
            """,
            (int(user_id), (type or "").strip(), int(ref_id) if ref_id is not None else None, (message or "").strip()),
        )
        conn.commit()
        new_id = int(cur.lastrowid)
        conn.close()
        return new_id

    def mark_read(self, notification_id: int, user_id: int) -> None:
        conn = _connect()
        cur = conn.cursor()
        cur.execute(
            "UPDATE notifications SET is_read = 1 WHERE id = ? AND user_id = ?",
            (int(notification_id), int(user_id)),
        )
        conn.commit()
        conn.close()

    def find_similar(
        self,
        *,
        company_id: int,
        text: str,
        limit: int = 5,
    ) -> List[Dict[str, object]]:
        conn = _connect()
        cur = conn.cursor()
        like = f"%{(text or '').strip()}%"
        rows = cur.execute(
            """
            SELECT id, titulo, tributo, competencia, tipo, orgao, status
            FROM tarefas
            WHERE company_id = ?
              AND (titulo LIKE ? OR tributo LIKE ?)
            ORDER BY competencia DESC, titulo COLLATE NOCASE
            LIMIT ?
            """,
            (int(company_id), like, like, int(limit)),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]


class ClassificationRepository:
    def create(
        self,
        *,
        task_id: Optional[int],
        user_id: Optional[int],
        filename: str,
        competencia: Optional[str],
        empresa: str,
        grupo: Optional[str],
        subgrupo: Optional[str],
        orgao: Optional[str],
        tributo: Optional[str],
        subtipo: Optional[str],
        acao: Optional[str],
        confianca: float,
        status: str,
        raw_text: str,
    ) -> int:
        conn = _connect()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO classificacoes (
                task_id, user_id, filename, competencia, empresa, grupo, subgrupo, orgao, tributo,
                subtipo, acao, confianca, status, raw_text, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """,
            (
                int(task_id) if task_id is not None else None,
                int(user_id) if user_id is not None else None,
                (filename or "").strip(),
                (competencia or "").strip() if competencia else None,
                (empresa or "").strip(),
                (grupo or "").strip() if grupo else None,
                (subgrupo or "").strip() if subgrupo else None,
                (orgao or "").strip() if orgao else None,
                (tributo or "").strip() if tributo else None,
                (subtipo or "").strip() if subtipo else None,
                (acao or "").strip() if acao else None,
                float(confianca or 0),
                (status or "").strip(),
                (raw_text or "").strip(),
            ),
        )
        conn.commit()
        new_id = int(cur.lastrowid)
        conn.close()
        return new_id


class SettingsRepository:
    def _get_json(self, key: str, default: Dict[str, object]) -> Dict[str, object]:
        conn = _connect()
        cur = conn.cursor()
        row = cur.execute("SELECT value FROM app_settings WHERE key = ?", (key,)).fetchone()
        conn.close()
        if not row:
            return dict(default)
        raw = str(row["value"] or "").strip()
        if not raw:
            return dict(default)
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                merged = dict(default)
                merged.update(parsed)
                return merged
        except Exception:
            pass
        return dict(default)

    def _set_json(self, key: str, value: Dict[str, object]) -> None:
        conn = _connect()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO app_settings (key, value, updated_at)
            VALUES (?, ?, datetime('now'))
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = excluded.updated_at
            """,
            (key, json.dumps(value, ensure_ascii=False)),
        )
        conn.commit()
        conn.close()

    def get_server(self) -> Dict[str, object]:
        return self._get_json(
            "server",
            {
                "server_host": "127.0.0.1",
                "server_port": 8000,
                "server_name": "41 Fiscal Hub API",
                "environment": "local",
            },
        )

    def set_server(self, payload: Dict[str, object]) -> Dict[str, object]:
        current = self.get_server()
        current.update(payload or {})
        if not current.get("server_port"):
            current["server_port"] = 8000
        self._set_json("server", current)
        return current

    def get_email(self) -> Dict[str, object]:
        return self._get_json(
            "email",
            {
                "smtp_host": "",
                "smtp_port": 587,
                "smtp_user": "",
                "smtp_pass": "",
                "smtp_sender": "",
                "smtp_tls": True,
            },
        )

    def set_email(self, payload: Dict[str, object]) -> Dict[str, object]:
        current = self.get_email()
        current.update(payload or {})
        if not current.get("smtp_port"):
            current["smtp_port"] = 587
        self._set_json("email", current)
        return current
