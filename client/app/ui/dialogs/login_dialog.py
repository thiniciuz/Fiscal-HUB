from __future__ import annotations

from typing import Optional, Tuple

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QComboBox,
    QLineEdit,
    QPushButton,
    QHBoxLayout,
    QDialogButtonBox,
    QMessageBox,
)

from app.db.repositories import UserRepository


class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Selecionar usuário")

        self.repo = UserRepository()

        lay = QVBoxLayout(self)
        form = QFormLayout()

        self.cmb_users = QComboBox()
        form.addRow("Usuário", self.cmb_users)

        add_row = QHBoxLayout()
        self.ed_new = QLineEdit()
        self.ed_new.setPlaceholderText("Novo usuário")
        self.btn_add = QPushButton("Adicionar")
        self.btn_add.clicked.connect(self._add_user)
        add_row.addWidget(self.ed_new, 1)
        add_row.addWidget(self.btn_add)
        form.addRow("", add_row)

        lay.addLayout(form)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

        self._selected: Optional[Tuple[int, str]] = None
        self._reload_users()

    def _reload_users(self) -> None:
        self.cmb_users.clear()
        users = self.repo.list()
        for u in users:
            self.cmb_users.addItem(str(u["nome"]), int(u["id"]))

        if self.cmb_users.count() == 0:
            QMessageBox.information(self, "Usuários", "Cadastre o primeiro usuário.")

    def _add_user(self) -> None:
        name = self.ed_new.text().strip()
        if not name:
            QMessageBox.warning(self, "Usuários", "Informe um nome de usuário.")
            return
        try:
            new_id = self.repo.create(name)
        except Exception as e:
            QMessageBox.warning(self, "Usuários", str(e))
            return
        self.ed_new.clear()
        self._reload_users()
        idx = self.cmb_users.findData(new_id)
        if idx >= 0:
            self.cmb_users.setCurrentIndex(idx)

    def _accept(self) -> None:
        if self.cmb_users.count() == 0:
            QMessageBox.warning(self, "Usuários", "Cadastre um usuário para continuar.")
            return
        user_id = self.cmb_users.currentData()
        name = self.cmb_users.currentText()
        if user_id is None:
            QMessageBox.warning(self, "Usuários", "Selecione um usuário.")
            return
        self._selected = (int(user_id), str(name))
        self.accept()

    @property
    def selected(self) -> Optional[Tuple[int, str]]:
        return self._selected
