"""Compat layer.

O projeto começou com um mock em memória. Agora as tarefas estão no SQLite.
Mantemos estas funções por compatibilidade, mas o caminho recomendado é usar
`TaskService` + modelos em `app.core.models`.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.core.competencia import fmt_comp, parse_comp_label, format_comp_label
from app.core.services import TaskService


_svc: Optional[TaskService] = None
_user_id: Optional[int] = None


def set_user(user_id: int) -> None:
    global _svc, _user_id
    _user_id = int(user_id)
    _svc = TaskService(_user_id)


def list_competencias(company_id: int, tipo: str) -> List[str]:
    if _svc is None:
        raise ValueError("Usuário não definido")
    return _svc.list_competencias(int(company_id), str(tipo))


def get_tarefas(
    company_id: int,
    tipo_tarefa: str,
    status: Optional[List[str]] = None,
    competencia: Optional[str] = None,
) -> List[Dict[str, Any]]:
    if _svc is None:
        raise ValueError("Usuário não definido")
    tasks = _svc.list_tasks(int(company_id), str(tipo_tarefa), status=status, competencia=competencia)
    # Mantém o formato de dicionário usado pela UI antiga
    return [
        {
            "id": t.id,
            "company_id": t.company_id,
            "titulo": t.titulo,
            "tipo": t.tipo,
            "orgao": t.orgao,
            "tributo": t.tributo,
            "competencia": fmt_comp(t.competencia) if t.competencia else "",
            "status": t.status,
        }
        for t in tasks
    ]


def update_status(tarefa_id: int, new_status: str) -> None:
    if _svc is None:
        raise ValueError("Usuário não definido")
    _svc.update_status(int(tarefa_id), str(new_status))
