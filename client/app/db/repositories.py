from __future__ import annotations

from typing import Dict, List, Optional

from app.core.models import Company, Task, TaskStatus, TaskType, TaskOrgao
from app.core.competencia import fmt_comp
from app.core.br_docs import only_digits, format_cnpj, sanitize_ie

from .sqlite import _connect


class UserRepository:
    def list(self) -> List[Dict[str, object]]:
        conn = _connect()
        cur = conn.cursor()
        rows = cur.execute("SELECT id, nome FROM usuarios ORDER BY nome COLLATE NOCASE").fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def create(self, nome: str) -> int:
        nome = (nome or "").strip()
        if not nome:
            raise ValueError("Nome do usuário é obrigatório")
        conn = _connect()
        cur = conn.cursor()
        cur.execute("INSERT INTO usuarios (nome) VALUES (?)", (nome,))
        conn.commit()
        new_id = int(cur.lastrowid)
        conn.close()
        return new_id

    def get(self, user_id: int) -> Optional[Dict[str, object]]:
        conn = _connect()
        cur = conn.cursor()
        row = cur.execute(
            "SELECT id, nome FROM usuarios WHERE id = ?",
            (int(user_id),),
        ).fetchone()
        conn.close()
        return dict(row) if row else None


class CompanyRepository:
    def __init__(self, user_id: int):
        self.user_id = int(user_id)

    def list(self, *, query: str = "", regime: Optional[str] = None) -> List[Company]:
        """Lista empresas com busca e filtro por regime.

        Observação: normaliza (TRIM + NOCASE) para evitar inconsistências de dados
        (ex.: "Lucro Real ").
        """
        conn = _connect()
        cur = conn.cursor()

        q = "SELECT id, nome, cnpj, ie, regime FROM empresas WHERE user_id = ?"
        params: list[object] = [int(self.user_id)]

        if regime and regime != "Todas":
            q += " AND TRIM(regime) = TRIM(?) COLLATE NOCASE"
            params.append(regime)

        s = (query or "").strip()
        if s:
            q += " AND (nome LIKE ? OR cnpj LIKE ?)"
            like = f"%{s}%"
            params.extend([like, like])

        q += " ORDER BY nome COLLATE NOCASE"
        rows = cur.execute(q, params).fetchall()
        conn.close()
        return [Company(**dict(r)) for r in rows]

    def get(self, company_id: int) -> Optional[Company]:
        conn = _connect()
        cur = conn.cursor()
        row = cur.execute(
            "SELECT id, nome, cnpj, ie, regime FROM empresas WHERE id = ? AND user_id = ?",
            (int(company_id), int(self.user_id)),
        ).fetchone()
        conn.close()
        return Company(**dict(row)) if row else None

    def create(self, *, nome: str, cnpj: str = "", ie: str = "", regime: str = "Simples Nacional") -> int:
        nome = (nome or "").strip()
        if not nome:
            raise ValueError("Nome da empresa é obrigatório")

        cnpj_fmt = format_cnpj(cnpj)
        # valida CNPJ (quando preenchido)
        if cnpj_fmt and len(only_digits(cnpj_fmt)) != 14:
            raise ValueError("CNPJ deve conter 14 dígitos")

        ie_num = sanitize_ie(ie)

        conn = _connect()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO empresas (user_id, nome, cnpj, ie, regime) VALUES (?, ?, ?, ?, ?)",
            (int(self.user_id), nome, (cnpj_fmt or "").strip(), (ie_num or "").strip(), (regime or "").strip()),
        )
        conn.commit()
        new_id = int(cur.lastrowid)
        conn.close()
        return new_id

    def update(self, company_id: int, *, cnpj: str, ie: str, regime: str) -> None:
        cnpj_fmt = format_cnpj(cnpj)
        if cnpj_fmt and len(only_digits(cnpj_fmt)) != 14:
            raise ValueError("CNPJ deve conter 14 dígitos")

        ie_num = sanitize_ie(ie)
        conn = _connect()
        cur = conn.cursor()
        cur.execute(
            "UPDATE empresas SET cnpj = ?, ie = ?, regime = ? WHERE id = ? AND user_id = ?",
            ((cnpj_fmt or "").strip(), (ie_num or "").strip(), (regime or "").strip(), int(company_id), int(self.user_id)),
        )
        conn.commit()
        conn.close()


class TaskRepository:
    """Repositório SQLite de tarefas.

    Mantém `competencia` no formato interno (YYYYMM). A UI pode usar `fmt_comp` para exibir.
    """

    def __init__(self, user_id: int):
        self.user_id = int(user_id)

    def list_competencias(self, company_id: int, tipo: TaskType) -> List[str]:
        conn = _connect()
        cur = conn.cursor()
        rows = cur.execute(
            """
            SELECT DISTINCT competencia
            FROM tarefas
            WHERE user_id = ? AND company_id = ? AND tipo = ? AND competencia IS NOT NULL AND competencia != ''
            ORDER BY competencia DESC
            """,
            (int(self.user_id), int(company_id), str(tipo)),
        ).fetchall()
        conn.close()
        labels = [fmt_comp(r[0]) for r in rows if r and r[0]]
        return ["(todas)"] + labels

    def list(
        self,
        *,
        company_id: int,
        tipo: TaskType,
        status: Optional[List[TaskStatus]] = None,
        competencia: Optional[str] = None,
    ) -> List[Task]:
        conn = _connect()
        cur = conn.cursor()

        q = (
            "SELECT id, company_id, titulo, tipo, orgao, tributo, competencia, status, pdf_path, pdf_blob "
            "FROM tarefas WHERE user_id = ? AND company_id = ? AND tipo = ?"
        )
        params: list[object] = [int(self.user_id), int(company_id), str(tipo)]

        if status:
            placeholders = ",".join("?" for _ in status)
            q += f" AND status IN ({placeholders})"
            params.extend([str(s) for s in status])

        if competencia:
            q += " AND competencia = ?"
            params.append(str(competencia))

        q += " ORDER BY competencia DESC, titulo COLLATE NOCASE"
        rows = cur.execute(q, params).fetchall()
        conn.close()
        return [Task(**dict(r)) for r in rows]

    def create(
        self,
        *,
        company_id: int,
        titulo: str,
        tipo: TaskType,
        orgao: TaskOrgao,
        tributo: str = "",
        competencia: Optional[str] = None,
        status: TaskStatus = "PENDENTE",
        pdf_path: Optional[str] = None,
        pdf_blob: Optional[bytes] = None,
    ) -> int:
        titulo = (titulo or "").strip()
        if not titulo:
            raise ValueError("Título da tarefa é obrigatório")

        conn = _connect()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO tarefas (user_id, company_id, titulo, tipo, orgao, tributo, competencia, status, pdf_path, pdf_blob)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(self.user_id),
                int(company_id),
                titulo,
                str(tipo),
                str(orgao),
                (tributo or "").strip(),
                (competencia or "").strip() if competencia else None,
                str(status),
                (pdf_path or "").strip() if pdf_path else None,
                pdf_blob,
            ),
        )
        conn.commit()
        new_id = int(cur.lastrowid)
        conn.close()
        return new_id

    def update_status(self, task_id: int, new_status: TaskStatus) -> None:
        conn = _connect()
        cur = conn.cursor()
        cur.execute(
            "UPDATE tarefas SET status = ? WHERE id = ? AND user_id = ?",
            (str(new_status), int(task_id), int(self.user_id)),
        )
        conn.commit()
        conn.close()

    def get(self, task_id: int) -> Optional[Task]:
        conn = _connect()
        cur = conn.cursor()
        row = cur.execute(
            "SELECT id, company_id, titulo, tipo, orgao, tributo, competencia, status, pdf_path, pdf_blob FROM tarefas WHERE id = ? AND user_id = ?",
            (int(task_id), int(self.user_id)),
        ).fetchone()
        conn.close()
        return Task(**dict(row)) if row else None

    def update(
        self,
        task_id: int,
        *,
        company_id: int,
        titulo: str,
        tipo: TaskType,
        orgao: TaskOrgao,
        tributo: str = "",
        competencia: Optional[str] = None,
        status: TaskStatus = "PENDENTE",
        pdf_path: Optional[str] = None,
        pdf_blob: Optional[bytes] = None,
    ) -> None:
        titulo = (titulo or "").strip()
        if not titulo:
            raise ValueError("Título da tarefa é obrigatório")

        conn = _connect()
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE tarefas
            SET company_id = ?, titulo = ?, tipo = ?, orgao = ?, tributo = ?, competencia = ?, status = ?, pdf_path = ?, pdf_blob = ?
            WHERE id = ? AND user_id = ?
            """,
            (
                int(company_id),
                titulo,
                str(tipo),
                str(orgao),
                (tributo or "").strip(),
                (competencia or "").strip() if competencia else None,
                str(status),
                (pdf_path or "").strip() if pdf_path else None,
                pdf_blob,
                int(task_id),
                int(self.user_id),
            ),
        )
        conn.commit()
        conn.close()

    def update_pdf_path(self, task_id: int, pdf_path: Optional[str]) -> None:
        conn = _connect()
        cur = conn.cursor()
        cur.execute(
            "UPDATE tarefas SET pdf_path = ? WHERE id = ? AND user_id = ?",
            ((pdf_path or "").strip() if pdf_path else None, int(task_id), int(self.user_id)),
        )
        conn.commit()
        conn.close()

    def update_pdf_blob(self, task_id: int, pdf_blob: Optional[bytes]) -> None:
        conn = _connect()
        cur = conn.cursor()
        cur.execute(
            "UPDATE tarefas SET pdf_blob = ? WHERE id = ? AND user_id = ?",
            (pdf_blob, int(task_id), int(self.user_id)),
        )
        conn.commit()
        conn.close()

    def count_by_status(self, *, company_id: Optional[int] = None) -> Dict[str, int]:
        """Conta tarefas por status (todas as empresas ou uma empresa específica)."""
        conn = _connect()
        cur = conn.cursor()
        if company_id is None:
            rows = cur.execute(
                "SELECT status, COUNT(1) as c FROM tarefas WHERE user_id = ? GROUP BY status",
                (int(self.user_id),),
            ).fetchall()
        else:
            rows = cur.execute(
                "SELECT status, COUNT(1) as c FROM tarefas WHERE user_id = ? AND company_id = ? GROUP BY status",
                (int(self.user_id), int(company_id)),
            ).fetchall()
        conn.close()
        return {str(r[0]): int(r[1]) for r in rows}

    def companies_with_status(self, status: str) -> List[Dict[str, object]]:
        """Lista empresas que têm tarefas no status informado (com contagem)."""
        conn = _connect()
        cur = conn.cursor()
        rows = cur.execute(
            """
            SELECT e.id, e.nome, COUNT(*) qtd
            FROM tarefas t
            JOIN empresas e ON e.id = t.company_id
            WHERE t.status = ? AND t.user_id = ?
            GROUP BY e.id, e.nome
            ORDER BY qtd DESC
            """,
            (str(status), int(self.user_id)),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def tasks_by_company_and_status(self, company_id: int, status: str) -> List[Task]:
        conn = _connect()
        cur = conn.cursor()
        rows = cur.execute(
            """
            SELECT id, company_id, titulo, tipo, orgao, tributo, competencia, status, pdf_path, pdf_blob
            FROM tarefas
            WHERE user_id = ? AND company_id = ? AND status = ?
            ORDER BY competencia DESC, titulo COLLATE NOCASE
            """,
            (int(self.user_id), int(company_id), str(status)),
        ).fetchall()
        conn.close()
        return [Task(**dict(r)) for r in rows]
