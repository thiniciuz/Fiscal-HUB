from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional


TaskType = Literal["OBR", "ACS"]
TaskOrgao = Literal["MUN", "EST", "FED"]
TaskStatus = Literal["PENDENTE", "EM_ANDAMENTO", "CONCLUIDA", "ENVIADA"]


@dataclass(frozen=True)
class Company:
    id: int
    nome: str
    cnpj: str = ""
    ie: str = ""
    regime: str = "Simples Nacional"


@dataclass(frozen=True)
class Task:
    id: int
    company_id: int
    titulo: str
    tipo: TaskType
    orgao: TaskOrgao
    tributo: str
    competencia: Optional[str] = None  # YYYYMM ou None
    status: TaskStatus = "PENDENTE"
    pdf_path: Optional[str] = None
    pdf_blob: Optional[bytes] = None
