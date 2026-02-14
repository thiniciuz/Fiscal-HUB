from __future__ import annotations

from typing import Optional, Callable

from PySide6.QtWidgets import (
    QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QFrame, QMessageBox, QFileDialog
)
from PySide6.QtCore import Qt

from app.core.models import Task
from app.core.lists import STATUS_ORDER, STATUS_LABELS
from app.core.competencia import fmt_comp
from pathlib import Path

from app.core.attachments import open_with_default_app, resolve_pdf_path, write_pdf_blob_to_temp
from app.db.repositories import TaskRepository


class DetailPanel(QFrame):
    def __init__(self, user_id: int, on_change_status=None, on_edit=None):
        super().__init__()
        self.on_change_status = on_change_status
        self.on_edit = on_edit
        self.user_id = int(user_id)
        self.task_id = None
        self.task: Optional[Task] = None

        # A aparência é controlada globalmente via app.core.style.APP_QSS

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(10)

        self.lbl_title = QLabel("Detalhes")
        self.lbl_title.setObjectName("Title")
        lay.addWidget(self.lbl_title)

        # Empty state elegante (Sugestão 5)
        self.empty_wrap = QFrame()
        self.empty_wrap.setObjectName("EmptyState")
        empty = QVBoxLayout(self.empty_wrap)
        empty.setContentsMargins(0, 18, 0, 18)
        empty.setSpacing(6)
        empty.addStretch(1)

        self.lbl_empty_icon = QLabel("⦿")
        self.lbl_empty_icon.setObjectName("EmptyIcon")
        self.lbl_empty_icon.setAlignment(Qt.AlignCenter)
        empty.addWidget(self.lbl_empty_icon)

        self.lbl_empty_title = QLabel("Selecione uma tarefa")
        self.lbl_empty_title.setObjectName("H2")
        self.lbl_empty_title.setAlignment(Qt.AlignCenter)
        empty.addWidget(self.lbl_empty_title)

        self.lbl_empty_caption = QLabel("Clique em um card para ver os detalhes")
        self.lbl_empty_caption.setObjectName("Caption")
        self.lbl_empty_caption.setAlignment(Qt.AlignCenter)
        self.lbl_empty_caption.setWordWrap(True)
        empty.addWidget(self.lbl_empty_caption)

        empty.addStretch(1)
        lay.addWidget(self.empty_wrap)

        # Conteúdo (quando há tarefa)
        self.lbl_info = QLabel("")
        self.lbl_info.setObjectName("Muted")
        self.lbl_info.setWordWrap(True)
        self.lbl_info.setVisible(False)
        lay.addWidget(self.lbl_info)

        # Ações
        actions = QHBoxLayout()
        actions.setSpacing(8)
        lay.addLayout(actions)

        self.btn_pdf = QPushButton("+")
        self.btn_pdf.setProperty("role", "secondary")
        self.btn_pdf.clicked.connect(self._handle_pdf_click)
        self.btn_pdf.setVisible(False)
        actions.addWidget(self.btn_pdf)

        self.btn_edit = QPushButton("…")
        self.btn_edit.setProperty("role", "secondary")
        self.btn_edit.clicked.connect(self._edit)
        self.btn_edit.setVisible(False)
        actions.addWidget(self.btn_edit)

        actions.addStretch(1)

        self.row_btns = QHBoxLayout()
        self.row_btns.setSpacing(8)
        lay.addLayout(self.row_btns)

        self._btns = []
        for s in STATUS_ORDER:
            b = QPushButton(STATUS_LABELS[s])
            b.setProperty("role", "status")
            b.setProperty("status", s)
            b.clicked.connect(lambda _, st=s: self._change(st))
            self._btns.append(b)
            self.row_btns.addWidget(b)

        self.row_btns.addStretch(1)
        self._enable_buttons(False)

    def _enable_buttons(self, enabled: bool):
        for b in self._btns:
            b.setEnabled(enabled and callable(self.on_change_status))

    def set_task(self, task: Optional[Task]):
        self.task = task
        self.empty_wrap.setVisible(task is None)
        self.lbl_info.setVisible(task is not None)
        if not task:
            self.task_id = None
            self.lbl_title.setText("Detalhes")
            self.lbl_info.setText("Selecione uma tarefa")
            self._enable_buttons(False)
            self.btn_pdf.setVisible(False)
            self.btn_edit.setVisible(False)
            return

        self.task_id = task.id
        titulo = task.titulo or "—"
        comp = fmt_comp(task.competencia)
        status = task.status or ""
        trib = task.tributo or ""
        org = task.orgao or ""

        self.lbl_title.setText(titulo)
        pdf_line = ""
        pdf_name = task.pdf_path or ""
        if task.pdf_blob or task.pdf_path:
            pdf_line = f"\nPDF: {pdf_name or '(anexo)'}"
        self.lbl_info.setText(
            f"Competência: {comp}\nTributo: {trib}\nÓrgão: {org}\nStatus: {status}{pdf_line}"
        )
        self._enable_buttons(True)
        if task.pdf_blob or task.pdf_path:
            self.btn_pdf.setText(pdf_name or "PDF")
        else:
            self.btn_pdf.setText("+")
        self.btn_pdf.setVisible(True)
        self.btn_edit.setVisible(callable(self.on_edit))

    def _change(self, new_status: str):
        if not self.task_id or not callable(self.on_change_status):
            return
        self.on_change_status(int(self.task_id), new_status)

    def _handle_pdf_click(self):
        if not self.task or not (self.task.pdf_path or self.task.pdf_blob):
            self._relink_pdf()
            return
        try:
            if self.task.pdf_blob:
                data = self.task.pdf_blob
                if isinstance(data, memoryview):
                    data = data.tobytes()
                name = self.task.pdf_path or f"task_{self.task.id}.pdf"
                p = write_pdf_blob_to_temp(data, name)
                open_with_default_app(str(p))
            else:
                p = resolve_pdf_path(self.task.pdf_path)
                if not p.exists():
                    raise FileNotFoundError(f"PDF não encontrado: {p}")
                open_with_default_app(str(p))
        except Exception as e:
            msg = str(e)
            resp = QMessageBox.question(
                self,
                "PDF",
                f"{msg}\n\nDeseja localizar o PDF novamente?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if resp != QMessageBox.Yes:
                return
            self._relink_pdf()

    def _relink_pdf(self) -> None:
        if not self.task_id:
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar PDF",
            "",
            "PDF (*.pdf)",
        )
        if not path:
            return
        if not path.lower().endswith(".pdf"):
            QMessageBox.warning(self, "PDF", "Selecione um arquivo .pdf")
            return
        try:
            with open(path, "rb") as f:
                data = f.read()
            name = Path(path).name
            repo = TaskRepository(self.user_id)
            repo.update_pdf_path(int(self.task_id), name)
            repo.update_pdf_blob(int(self.task_id), data)
            updated = repo.get(int(self.task_id))
            if updated:
                self.set_task(updated)
        except Exception as e:
            QMessageBox.warning(self, "PDF", str(e))

    def _edit(self):
        if not self.task or not callable(self.on_edit):
            return
        self.on_edit(self.task)
