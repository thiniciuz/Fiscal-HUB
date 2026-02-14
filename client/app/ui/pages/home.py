from __future__ import annotations

from PySide6.QtCore import Qt, QRegularExpression
from PySide6.QtGui import QRegularExpressionValidator
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QFrame, QSplitter, QMessageBox, QDialog
)

from app.core.state import AppState
from app.core.competencia import parse_comp_label
from app.core.services import TaskService
from app.db.repositories import CompanyRepository
from app.ui.components.filter_bar import FilterBar
from app.ui.components.card_grid import CardGrid
from app.ui.components.detail_panel import DetailPanel
from app.ui.dialogs.task_dialog import TaskDialog
from app.core.models import Task
from app.core.lists import REGIMES, STATUS_ORDER


class HomePage(QWidget):
    """Dashboard da empresa."""

    def __init__(self, state: AppState, on_back=None):
        super().__init__()
        self.state = state
        self.on_back = on_back

        if self.state.current_user_id is None:
            raise ValueError("Usuário não definido")
        self.company_repo = CompanyRepository(int(self.state.current_user_id))
        self.task_service = TaskService(int(self.state.current_user_id))

        self._tipo = "OBR"              # OBR | ACS
        self._status = ["PENDENTE"]     # lista
        self._competencia = None        # YYYYMM | None
        self._company_id = None         # int | None
        self._dirty = False

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)

        # Top bar removida (evita elementos sem propósito visual / "remendo")

        # Company title
        self.lbl_company = QLabel("—")
        self.lbl_company.setObjectName("H0")
        root.addWidget(self.lbl_company)

        # Editable header: CNPJ / IE / Regime + ✔
        hdr = QHBoxLayout()
        hdr.setSpacing(10)

        lbl_cnpj = QLabel("CNPJ")
        lbl_cnpj.setObjectName("Accent")
        hdr.addWidget(lbl_cnpj)
        self.ed_cnpj = QLineEdit()
        self.ed_cnpj.setFixedWidth(180)
        # CNPJ: máscara (14 dígitos) + pontuação automática
        self.ed_cnpj.setInputMask("00.000.000/0000-00;_")
        self.ed_cnpj.textChanged.connect(self._mark_dirty)
        hdr.addWidget(self.ed_cnpj)

        lbl_ie = QLabel("IE")
        lbl_ie.setObjectName("Accent")
        hdr.addWidget(lbl_ie)
        self.ed_ie = QLineEdit()
        self.ed_ie.setFixedWidth(140)
        # IE: somente números
        self.ed_ie.setValidator(QRegularExpressionValidator(QRegularExpression(r"^\d{0,20}$")))
        self.ed_ie.textChanged.connect(self._mark_dirty)
        hdr.addWidget(self.ed_ie)

        lbl_reg = QLabel("Regime")
        lbl_reg.setObjectName("Accent")
        hdr.addWidget(lbl_reg)
        self.cmb_regime = QComboBox()
        self.cmb_regime.addItems(REGIMES)
        self.cmb_regime.currentIndexChanged.connect(self._mark_dirty)
        self.cmb_regime.setFixedWidth(180)
        hdr.addWidget(self.cmb_regime)

        hdr.addStretch(1)

        self.btn_save = QPushButton("✔")
        self.btn_save.setFixedSize(44, 34)
        self.btn_save.clicked.connect(self._save_company)
        self.btn_save.setVisible(False)
        self.btn_save.setEnabled(False)
        hdr.addWidget(self.btn_save)

        root.addLayout(hdr)

        # Tabs
        tabs = QHBoxLayout()
        tabs.setSpacing(8)

        self.btn_obr = QPushButton("Obrigações")
        self.btn_obr.setCheckable(True)
        self.btn_obr.setChecked(True)
        self.btn_obr.clicked.connect(lambda: self._set_tipo("OBR"))

        self.btn_acs = QPushButton("Acessórias")
        self.btn_acs.setCheckable(True)
        self.btn_acs.setChecked(False)
        self.btn_acs.clicked.connect(lambda: self._set_tipo("ACS"))

        tabs.addWidget(self.btn_obr)
        tabs.addWidget(self.btn_acs)
        tabs.addStretch(1)
        root.addLayout(tabs)

        # Filter bar wrap
        self.filter_wrap = QFrame()
        self.filter_wrap.setObjectName("Card")
        self.filter_lay = QVBoxLayout(self.filter_wrap)
        self.filter_lay.setContentsMargins(12, 10, 12, 10)
        self.filter_lay.setSpacing(8)
        root.addWidget(self.filter_wrap)

        # Main body
        self.split = QSplitter(Qt.Horizontal)
        self.split.setChildrenCollapsible(False)

        self.left_card = QFrame()
        self.left_card.setObjectName("Card")
        left_lay = QVBoxLayout(self.left_card)
        left_lay.setContentsMargins(12, 12, 12, 12)
        left_lay.setSpacing(10)

        self.grid = CardGrid([], on_click=self._open_detail)
        left_lay.addWidget(self.grid, 1)

        self.detail = DetailPanel(int(self.state.current_user_id), self._change_status, on_edit=self._edit_task)
        self.detail.setObjectName("Card")

        self.split.addWidget(self.left_card)
        self.split.addWidget(self.detail)
        self.split.setSizes([780, 320])

        root.addWidget(self.split, 1)

        if getattr(self.state, "selected_company_id", None):
            self.set_company(self.state.selected_company_id)

    def _go_back(self):
        if self.on_back:
            self.on_back()

    def set_company(self, company_id: int):
        self._company_id = int(company_id)
        # mantém estado compartilhado (ex.: reabrir última empresa)
        try:
            self.state.selected_company_id = self._company_id
        except Exception:
            pass

        company = self.company_repo.get(self._company_id)
        nome = (company.nome if company else "").strip() or "—"
        cnpj = company.cnpj if company else ""
        ie = company.ie if company else ""
        regime = company.regime if company else "Simples Nacional"

        self.lbl_company.setText(nome)

        self._dirty = False
        self.btn_save.setVisible(False)
        self.btn_save.setEnabled(False)

        self.ed_cnpj.blockSignals(True)
        self.ed_ie.blockSignals(True)
        self.cmb_regime.blockSignals(True)

        self.ed_cnpj.setText(cnpj)
        self.ed_ie.setText(ie)
        idx = self.cmb_regime.findText(regime)
        self.cmb_regime.setCurrentIndex(idx if idx >= 0 else 0)

        self.ed_cnpj.blockSignals(False)
        self.ed_ie.blockSignals(False)
        self.cmb_regime.blockSignals(False)

        self._rebuild_filter_bar()
        self._reload_cards()

    def _set_tipo(self, tipo: str):
        self._tipo = tipo
        self.btn_obr.setChecked(tipo == "OBR")
        self.btn_acs.setChecked(tipo == "ACS")
        self._rebuild_filter_bar()
        self._reload_cards()

    def _rebuild_filter_bar(self):
        while self.filter_lay.count():
            item = self.filter_lay.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        if not self._company_id:
            return

        comps = self.task_service.list_competencias(self._company_id, self._tipo)  # labels MM/AAAA
        self.filter_bar = FilterBar(comps, self._on_filters_change)
        self.filter_lay.addWidget(self.filter_bar)

    def _on_filters_change(self, status_list, comp_label):
        # Status vindo do FilterBar já costuma vir no formato interno
        self._status = status_list or list(STATUS_ORDER)
        self._competencia = parse_comp_label(comp_label)
        self._reload_cards()

    def _reload_cards(self):
        if not self._company_id:
            return

        tarefas = self.task_service.list_tasks(
            self._company_id,
            tipo=self._tipo,
            status=self._status,
            competencia=self._competencia,
        )
        self.grid.set_items(tarefas)
        self.detail.set_task(None)

    def _open_detail(self, task: Task):
        self.detail.set_task(task)

    def _change_status(self, task_id: int, new_status: str):
        self.task_service.update_status(int(task_id), str(new_status))
        self._reload_cards()

    def _edit_task(self, task: Task):
        dlg = TaskDialog(int(self.state.current_user_id), self, task=task)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._reload_cards()
            # re-seleciona a tarefa (com pdf_path atualizado)
            updated = None
            try:
                updated = self.task_service.repo.get(task.id)  # type: ignore[attr-defined]
            except Exception:
                updated = None
            self.detail.set_task(updated or task)

    def _mark_dirty(self, *_):
        if not self._company_id:
            return
        self._dirty = True
        self.btn_save.setVisible(True)
        self.btn_save.setEnabled(True)

    def _save_company(self):
        if not self._company_id:
            return

        try:
            self.company_repo.update(
                self._company_id,
                cnpj=self.ed_cnpj.text().strip(),
                ie=self.ed_ie.text().strip(),
                regime=self.cmb_regime.currentText().strip(),
            )
        except ValueError as e:
            QMessageBox.warning(self, "Dados inválidos", str(e))
            return

        self._dirty = False
        self.btn_save.setVisible(False)
        self.btn_save.setEnabled(False)

    # Exposto para a MainWindow atualizar depois de criar tarefas
    def reload_tasks(self):
        if not self._company_id:
            return
        self._rebuild_filter_bar()
        self._reload_cards()
