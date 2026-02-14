from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QRegularExpression
from PySide6.QtGui import QRegularExpressionValidator
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QFrame, QHBoxLayout, QPushButton,
    QDialog, QFormLayout, QLineEdit, QComboBox, QDialogButtonBox, QMessageBox
)

from app.core.lists import REGIMES
from app.db.repositories import CompanyRepository
from app.ui.dialogs.task_dialog import TaskDialog


class AddCompanyDialog(QDialog):
    def __init__(self, user_id: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Adicionar empresa")
        self.repo = CompanyRepository(int(user_id))

        lay = QVBoxLayout(self)
        form = QFormLayout()

        self.ed_nome = QLineEdit()
        self.ed_cnpj = QLineEdit()
        self.ed_ie = QLineEdit()

        # CNPJ (14 dígitos) com máscara: 00.000.000/0000-00
        self.ed_cnpj.setInputMask("00.000.000/0000-00;_")
        # IE: somente números (até 20 dígitos)
        self.ed_ie.setValidator(QRegularExpressionValidator(QRegularExpression(r"^\d{0,20}$")))
        self.cmb_regime = QComboBox()
        self.cmb_regime.addItems(REGIMES)  # sem "Todas"

        form.addRow("Nome", self.ed_nome)
        form.addRow("CNPJ", self.ed_cnpj)
        form.addRow("IE", self.ed_ie)
        form.addRow("Regime", self.cmb_regime)

        lay.addLayout(form)

        btns = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        # Botões com "ícones" (emoji) para combinar com o estilo do app
        _save_btn = btns.button(QDialogButtonBox.Save)
        if _save_btn:
            _save_btn.setText("✔")
            _save_btn.setToolTip("Salvar")
        _cancel_btn = btns.button(QDialogButtonBox.Cancel)
        if _cancel_btn:
            _cancel_btn.setText("❌")
            _cancel_btn.setToolTip("Cancelar")

        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

        self.new_id: Optional[int] = None

    def _save(self):
        try:
            self.new_id = self.repo.create(
                nome=self.ed_nome.text(),
                cnpj=self.ed_cnpj.text(),
                ie=self.ed_ie.text(),
                regime=self.cmb_regime.currentText(),
            )
        except Exception as e:
            QMessageBox.warning(self, "Erro", str(e))
            return
        self.accept()


 


class SettingsPage(QWidget):
    """Tela de Configurações."""

    def __init__(self, user_id: int, on_created=None):
        super().__init__()
        self.on_created = on_created
        self.user_id = int(user_id)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)

        title = QLabel("Configurações")
        title.setObjectName("H0")
        root.addWidget(title)

        card = QFrame()
        card.setObjectName("Card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(12)

        info = QLabel("Ações rápidas")
        info.setObjectName("H2")
        lay.addWidget(info)

        row = QHBoxLayout()
        row.setSpacing(10)

        self.btn_add_company = QPushButton("Adicionar nova empresa")
        self.btn_add_company.clicked.connect(self._add_company)
        row.addWidget(self.btn_add_company)

        self.btn_add_task = QPushButton("Adicionar nova tarefa")
        self.btn_add_task.clicked.connect(self._add_task)
        row.addWidget(self.btn_add_task)

        row.addStretch(1)
        lay.addLayout(row)

        root.addWidget(card)
        root.addStretch(1)

    def _add_company(self):
        dlg = AddCompanyDialog(self.user_id, self)
        if dlg.exec() == QDialog.Accepted:
            if self.on_created:
                self.on_created("company", dlg.new_id)

    def _add_task(self):
        dlg = TaskDialog(self.user_id, self)
        if dlg.exec() == QDialog.Accepted:
            if self.on_created:
                self.on_created("task", dlg.new_id)
