from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QTableWidget, QTableWidgetItem
)

from app.db.repositories import CompanyRepository
from app.core.lists import REGIMES_ALL as REGIMES


class CompaniesPage(QWidget):
    """Tela de Empresas (listagem + filtro + busca)."""

    def __init__(self, user_id: int, on_select_company):
        super().__init__()
        self.on_select_company = on_select_company

        self.company_repo = CompanyRepository(int(user_id))

        self._regime_filter = "Todas"
        self._search_text = ""

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)

        header = QHBoxLayout()
        self.lbl_title = QLabel("Empresas")
        self.lbl_title.setObjectName("H1")
        header.addWidget(self.lbl_title)

        header.addStretch(1)

        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("Buscar por cliente ou CNPJ...")
        self.txt_search.textChanged.connect(self._on_search)
        self.txt_search.setFixedWidth(360)
        header.addWidget(self.txt_search)

        root.addLayout(header)

        chips = QHBoxLayout()
        chips.setSpacing(8)

        # Chips: "Todas" + regimes cadastráveis (lista centralizada)
        self._chip_buttons = []
        self.btn_all = self._chip("Todas", True, lambda: self._set_regime("Todas"))
        self._chip_buttons.append(self.btn_all)
        chips.addWidget(self.btn_all)

        for reg in REGIMES[1:]:
            b = self._chip(reg, False, lambda r=reg: self._set_regime(r))
            self._chip_buttons.append(b)
            chips.addWidget(b)
        chips.addStretch(1)

        root.addLayout(chips)

        self.lbl_count = QLabel("")
        self.lbl_count.setObjectName("Muted")
        root.addWidget(self.lbl_count)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Cliente", "CNPJ", "IE", "Regime"])
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.setFocusPolicy(Qt.NoFocus)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.table.setSortingEnabled(False)

        self.table.cellDoubleClicked.connect(self._open_selected)
        root.addWidget(self.table, 1)

        # Empty state (melhor UX quando filtros/busca não retornam itens)
        self.empty = QWidget()
        empty_lay = QVBoxLayout(self.empty)
        empty_lay.setContentsMargins(0, 24, 0, 24)
        empty_lay.setSpacing(6)
        empty_lay.addStretch(1)
        self.empty_title = QLabel("Nenhuma empresa encontrada")
        self.empty_title.setAlignment(Qt.AlignCenter)
        self.empty_title.setObjectName("H2")
        empty_lay.addWidget(self.empty_title)
        self.empty_caption = QLabel("Ajuste os filtros ou a busca para ver resultados")
        self.empty_caption.setAlignment(Qt.AlignCenter)
        self.empty_caption.setObjectName("Caption")
        empty_lay.addWidget(self.empty_caption)
        empty_lay.addStretch(1)
        root.addWidget(self.empty, 1)
        self.empty.hide()

        # Botão "Abrir" removido: duplo clique já faz a ação principal e evita redundância.

        self.reload()

    def _chip(self, text: str, checked: bool, on_click):
        b = QPushButton(text)
        b.setCheckable(True)
        b.setChecked(checked)
        # Importante: clicked(bool) envia um argumento. Se conectarmos direto em
        # um lambda/fun��o sem par�metros, o PySide pode gerar TypeError e o filtro
        # deixa de funcionar. Envolvemos para ignorar o argumento.
        b.clicked.connect(lambda _=False, fn=on_click: fn())
        # Estilo de "chip" (para ter :checked / :pressed consistente)
        b.setProperty("role", "chip")
        return b

    def _set_regime(self, regime: str):
        self._regime_filter = regime

        for b in getattr(self, "_chip_buttons", []):
            b.setChecked(False)

        # Marca o selecionado
        if regime == "Todas":
            self.btn_all.setChecked(True)
        else:
            for b in getattr(self, "_chip_buttons", []):
                if b.text() == regime:
                    b.setChecked(True)
                    break

        self.reload()

    def _on_search(self, text: str):
        self._search_text = (text or "").strip()
        self.reload()

    def reload(self):
        # usa sqlite para filtro por regime e busca
        regime = None if self._regime_filter == "Todas" else self._regime_filter
        items = self.company_repo.list(query=self._search_text, regime=regime)

        # Empty state
        if not items:
            self.table.hide()
            self.empty.show()
        else:
            self.empty.hide()
            self.table.show()

        self.lbl_count.setText(f"{len(items)} empresas")
        self.table.setRowCount(len(items))

        self.table.setColumnWidth(0, 520)
        self.table.setColumnWidth(1, 170)
        self.table.setColumnWidth(2, 90)
        self.table.setColumnWidth(3, 140)

        for r, it in enumerate(items):
            cid = it.id
            cliente = (it.nome or "").strip()
            cnpj = it.cnpj or ""
            ie = it.ie or ""
            regime_txt = it.regime or ""

            i0 = QTableWidgetItem(cliente)
            i0.setData(Qt.UserRole, cid)

            i1 = QTableWidgetItem(cnpj)
            i2 = QTableWidgetItem(ie)
            i3 = QTableWidgetItem(regime_txt)

            for i in (i0, i1, i2, i3):
                i.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)

            self.table.setItem(r, 0, i0)
            self.table.setItem(r, 1, i1)
            self.table.setItem(r, 2, i2)
            self.table.setItem(r, 3, i3)

            # Sugestão 4 (listas longas): linhas mais compactas e confortáveis
            self.table.setRowHeight(r, 34)

    def _open_selected(self, *_):
        row = self.table.currentRow()
        if row < 0:
            return
        item = self.table.item(row, 0)
        if not item:
            return
        company_id = item.data(Qt.UserRole)
        if company_id:
            self.on_select_company(int(company_id))

