from __future__ import annotations

from typing import List, Optional

from app.core.models import Task, TaskStatus, TaskType
from app.db.repositories import TaskRepository


class TaskService:
    """Camada de regras de negócio para tarefas.

    Mantém a UI desacoplada do repositório e centraliza filtros/validações.
    """

    def __init__(self, user_id: Optional[int] = None, repo: Optional[TaskRepository] = None):
        if repo:
            self.repo = repo
        else:
            if user_id is None:
                raise ValueError("user_id é obrigatório")
            self.repo = TaskRepository(int(user_id))

    def list_competencias(self, company_id: int, tipo: TaskType) -> List[str]:
        return self.repo.list_competencias(company_id, tipo)

    def list_tasks(
        self,
        company_id: int,
        tipo: TaskType,
        status: Optional[List[str]] = None,
        competencia: Optional[str] = None,
    ) -> List[Task]:
        st: Optional[List[TaskStatus]] = None
        if status:
            st = [s for s in status]  # type: ignore[list-item]
        return self.repo.list(company_id=company_id, tipo=tipo, status=st, competencia=competencia)

    def update_status(self, task_id: int, new_status: str) -> None:
        self.repo.update_status(task_id, new_status)  # type: ignore[arg-type]
