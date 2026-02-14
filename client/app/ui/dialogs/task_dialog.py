from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QRegularExpression
from PySide6.QtGui import QRegularExpressionValidator
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QLineEdit,
    QComboBox,
    QDialogButtonBox,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QFileDialog,
    QMessageBox,
)

from app.core.lists import STATUS_ORDER, STATUS_LABELS, REGIMES
from app.core.models import Task, TaskType, TaskOrgao, TaskStatus
from app.core.competencia import parse_comp_label, fmt_comp
from app.core.attachments import safe_remove
from app.db.sqlite import get_attachments_dir
from app.db.repositories import CompanyRepository, TaskRepository


def _parse_comp_any(s: str) -> Optional[str]:
    """Aceita 'MM/AAAA'. Retorna internal 'YYYYMM' ou None."""
    txt = (s or "").strip()
    if not txt:
        return None
    return parse_comp_label(txt)


def _is_managed_attachment(path: str) -> bool:
    """Garante que sÃ³ apagamos PDFs que o app gerencia (pasta attachments do APPDATA)."""
    if not path:
        return False
    try:
        base = str(get_attachments_dir().resolve())
        p = Path(path)
        if not p.is_absolute():
            p = get_attachments_dir() / p
        target = str(p.resolve())
        # commonpath Ã© mais seguro que startswith (evita falsos positivos do tipo .../attachments2)
        import os
        return (
            Path(target).suffix.lower() == ".pdf"
            and os.path.commonpath([base, target]) == base
        )
    except Exception:
        return False


class TaskDialog(QDialog):
    """Dialog de criaÃ§Ã£o/ediÃ§Ã£o de tarefa com anexo PDF opcional (mÃ¡x 1 por tarefa)."""

    def __init__(self, user_id: int, parent=None, task: Optional[Task] = None):
        super().__init__(parent)
        self.setWindowTitle("Editar tarefa" if task else "Adicionar tarefa")

        self.company_repo = CompanyRepository(int(user_id))
        self.task_repo = TaskRepository(int(user_id))

        self._task = task
        self.new_id: Optional[int] = None

        # Estado do PDF:
        # - _selected_pdf: caminho de origem escolhido pelo usuÃ¡rio (a ser lido e salvo no DB)
        # - _clear_pdf: usuÃ¡rio pediu remover anexo
        self._selected_pdf: Optional[str] = None
        self._clear_pdf = False

        lay = QVBoxLayout(self)
        form = QFormLayout()

        self.cmb_company = QComboBox()
        self._companies = self.company_repo.list()
        for c in self._companies:
            self.cmb_company.addItem(c.nome, c.id)

        self.ed_titulo = QLineEdit()

        self.cmb_tipo = QComboBox()
        self.cmb_tipo.addItem("ObrigaÃ§Ã£o", "OBR")
        self.cmb_tipo.addItem("AcessÃ³ria", "ACS")

        self.cmb_orgao = QComboBox()
        self.cmb_orgao.addItem("Municipal", "MUN")
        self.cmb_orgao.addItem("Estadual", "EST")
        self.cmb_orgao.addItem("Federal", "FED")

        self.ed_tributo = QLineEdit()
        self.ed_comp = QLineEdit()
        self.ed_comp.setPlaceholderText("MM/AAAA")
        self.ed_comp.textChanged.connect(self._on_comp_changed)

        self.cmb_status = QComboBox()
        for s in STATUS_ORDER:
            self.cmb_status.addItem(STATUS_LABELS[s], s)

        # PDF (opcional)
        pdf_row = QHBoxLayout()
        self.lbl_pdf = QLabel("(nenhum)")
        self.lbl_pdf.setObjectName("Muted")
        self.btn_pick_pdf = QPushButton("Selecionar PDFâ€¦")
        self.btn_pick_pdf.clicked.connect(self._pick_pdf)
        self.btn_clear_pdf = QPushButton("Remover")
        self.btn_clear_pdf.setVisible(False)
        self.btn_clear_pdf.clicked.connect(self._clear_pdf_clicked)
        pdf_row.addWidget(self.lbl_pdf, 1)
        pdf_row.addWidget(self.btn_pick_pdf)
        pdf_row.addWidget(self.btn_clear_pdf)

        form.addRow("Empresa", self.cmb_company)
        form.addRow("TÃ­tulo", self.ed_titulo)
        form.addRow("Tipo", self.cmb_tipo)
        form.addRow("Ã“rgÃ£o", self.cmb_orgao)
        form.addRow("Tributo", self.ed_tributo)
        form.addRow("CompetÃªncia", self.ed_comp)
        form.addRow("Status", self.cmb_status)
        form.addRow("PDF (opcional)", pdf_row)

        lay.addLayout(form)

        btns = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        # BotÃµes com "Ã­cones" (emoji) para combinar com o estilo do app
        _save_btn = btns.button(QDialogButtonBox.Save)
        if _save_btn:
            _save_btn.setText("âœ”")
            _save_btn.setToolTip("Salvar")
        _cancel_btn = btns.button(QDialogButtonBox.Cancel)
        if _cancel_btn:
            _cancel_btn.setText("âŒ")
            _cancel_btn.setToolTip("Cancelar")

        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

        if task:
            self._prefill(task)

    def _prefill(self, task: Task) -> None:
        idx = self.cmb_company.findData(task.company_id)
        if idx >= 0:
            self.cmb_company.setCurrentIndex(idx)

        self.ed_titulo.setText(task.titulo or "")
        self.cmb_tipo.setCurrentIndex(0 if task.tipo == "OBR" else 1)
        self.cmb_orgao.setCurrentIndex({"MUN": 0, "EST": 1, "FED": 2}.get(task.orgao, 0))
        self.ed_tributo.setText(task.tributo or "")
        self.ed_comp.setText(fmt_comp(task.competencia) if task.competencia else "")
        sidx = self.cmb_status.findData(task.status)
        if sidx >= 0:
            self.cmb_status.setCurrentIndex(sidx)

        # PDF atual
        if task.pdf_blob or task.pdf_path:
            name = Path(task.pdf_path).name if task.pdf_path else "(anexo)"
            self.lbl_pdf.setText(name)
            self.btn_clear_pdf.setVisible(True)
        else:
            self.lbl_pdf.setText("(nenhum)")
            self.btn_clear_pdf.setVisible(False)

    def _pick_pdf(self) -> None:
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

        self._selected_pdf = path
        self._clear_pdf = False
        self.lbl_pdf.setText(Path(path).name)
        self.btn_clear_pdf.setVisible(True)

    def _clear_pdf_clicked(self) -> None:
        self._selected_pdf = None
        self._clear_pdf = True
        self.lbl_pdf.setText("(nenhum)")
        self.btn_clear_pdf.setVisible(False)

    def _on_comp_changed(self, text: str) -> None:
        # Auto-inserir "/" apÃ³s MM
        t = text.strip()
        if len(t) == 2 and t.isdigit():
            self.ed_comp.blockSignals(True)
            self.ed_comp.setText(f"{t}/")
            self.ed_comp.setCursorPosition(3)
            self.ed_comp.blockSignals(False)

    def _save(self) -> None:
        try:
            raw_company_id = self.cmb_company.currentData()
            if raw_company_id is None:
                raise ValueError("Selecione uma empresa antes de salvar a tarefa.")
            company_id = int(raw_company_id)
            titulo = self.ed_titulo.text().strip()
            tipo: TaskType = str(self.cmb_tipo.currentData())  # type: ignore[assignment]
            orgao: TaskOrgao = str(self.cmb_orgao.currentData())  # type: ignore[assignment]
            tributo = self.ed_tributo.text().strip()
            comp_raw = self.ed_comp.text()
            comp = _parse_comp_any(comp_raw)
            if comp_raw.strip() and comp is None:
                raise ValueError("Competência inválida. Use MM/AAAA.")
            status: TaskStatus = str(self.cmb_status.currentData())  # type: ignore[assignment]

            # Resolve pdf_path final
            pdf_path_final: Optional[str] = None
            pdf_blob_final: Optional[bytes] = None
            old_pdf: Optional[str] = self._task.pdf_path if self._task else None
            old_blob: Optional[bytes] = self._task.pdf_blob if self._task else None

            if self._clear_pdf:
                pdf_path_final = None
                pdf_blob_final = None
            elif self._selected_pdf:
                with open(self._selected_pdf, "rb") as f:
                    pdf_blob_final = f.read()
                pdf_path_final = Path(self._selected_pdf).name
            else:
                pdf_path_final = old_pdf
                pdf_blob_final = old_blob

            if self._task:
                self.task_repo.update(
                    self._task.id,
                    company_id=company_id,
                    titulo=titulo,
                    tipo=tipo,
                    orgao=orgao,
                    tributo=tributo,
                    competencia=comp,
                    status=status,
                    pdf_path=pdf_path_final,
                    pdf_blob=pdf_blob_final,
                )

                # Se trocou ou removeu PDF, apaga o antigo para nÃ£o acumular anexos.
                if (
                    old_pdf
                    and (self._clear_pdf or (pdf_path_final and pdf_path_final != old_pdf))
                    and _is_managed_attachment(old_pdf)
                ):
                    safe_remove(old_pdf)

                self.new_id = int(self._task.id)
            else:
                self.new_id = self.task_repo.create(
                    company_id=company_id,
                    titulo=titulo,
                    tipo=tipo,
                    orgao=orgao,
                    tributo=tributo,
                    competencia=comp,
                    status=status,
                    pdf_path=pdf_path_final,
                    pdf_blob=pdf_blob_final,
                )

        except Exception as e:
            QMessageBox.warning(self, "Erro", str(e))
            return

        self.accept()

