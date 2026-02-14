from __future__ import annotations

from typing import List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton, QComboBox

from app.core.lists import STATUS_ORDER, STATUS_LABELS
from app.core.competencia import label_from_comp


class FilterBar(QWidget):
    """Barra de filtros (Status + Competência).

    - Status: botões checkáveis (multi-select)
    - Competência: combo

    on_change: (status_list: List[str], comp_label: str)
    """

    def __init__(self, comps: List[str], on_change):
        super().__init__()
        self.on_change = on_change
        self._status_btns: List[QPushButton] = []

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        # Status
        lbl_status = QLabel("Status:")
        lbl_status.setObjectName("Accent")
        lay.addWidget(lbl_status, 0, Qt.AlignLeft)

        for s in STATUS_ORDER:
            b = QPushButton(STATUS_LABELS[s])
            b.setCheckable(True)
            b.setProperty("status", s)
            # default: só PENDENTE selecionado
            if s == "PENDENTE":
                b.setChecked(True)
            b.clicked.connect(self._emit)
            self._status_btns.append(b)
            lay.addWidget(b)

        lay.addStretch(1)

        # Competência
        lbl_comp = QLabel("Competência:")
        lbl_comp.setObjectName("Accent")
        lay.addWidget(lbl_comp)

        self.cmb_comp = QComboBox()
        self.cmb_comp.addItem("Todas")
        for c in comps:
            if not c:
                continue
            s = str(c).strip()
            # alguns providers já incluem a opção "(todas)"; evita duplicar
            if s.lower() in {"(todas)", "todas", "todos"}:
                continue
            self.cmb_comp.addItem(label_from_comp(s))
        self.cmb_comp.currentTextChanged.connect(lambda _: self._emit())
        lay.addWidget(self.cmb_comp)

    def status_list(self) -> List[str]:
        return [b.property("status") for b in self._status_btns if b.isChecked()]

    def selected_comp_label(self) -> str:
        return self.cmb_comp.currentText()

    def _emit(self):
        self.on_change(self.status_list(), self.selected_comp_label())
