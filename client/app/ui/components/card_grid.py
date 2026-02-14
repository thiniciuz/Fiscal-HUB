from __future__ import annotations

from typing import List, Callable, Optional

from PySide6.QtWidgets import QWidget, QVBoxLayout, QGridLayout, QLabel, QScrollArea
from PySide6.QtCore import Qt, Signal
from shiboken6 import isValid

from .task_card import TaskCard
from app.core.models import Task


class CardGrid(QWidget):
    task_selected = Signal(object)

    def __init__(self, items: Optional[List[Task]] = None, on_click: Optional[Callable] = None):
        super().__init__()
        self._items: List[Task] = items or []
        self._on_click = on_click
        self._selected_card = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.NoFrame)

        self.container = QWidget()
        self.grid = QGridLayout(self.container)
        self.grid.setContentsMargins(6, 6, 6, 6)
        # Sugestão 4: espaçamento levemente menor para reduzir fadiga em listas
        self.grid.setSpacing(10)
        # Mantém o conteúdo no topo para não esticar cards quando a grade tem poucos itens
        self.grid.setAlignment(Qt.AlignTop)

        self.scroll.setWidget(self.container)
        root.addWidget(self.scroll, 1)

        self._render()

    def set_items(self, items: List[Task]):
        self._items = items or []
        self._render()

    def _clear(self):
        self._selected_card = None
        while self.grid.count():
            item = self.grid.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _render(self):
        self._clear()

        if not self._items:
            # Empty state (Sugestão 5): mais elegante e com hierarquia
            wrap = QWidget()
            lay = QVBoxLayout(wrap)
            lay.setContentsMargins(0, 24, 0, 24)
            lay.setSpacing(6)
            lay.addStretch(1)

            title = QLabel("Nenhuma tarefa encontrada")
            title.setAlignment(Qt.AlignCenter)
            title.setObjectName("H2")
            lay.addWidget(title)

            caption = QLabel("Ajuste os filtros ou crie uma nova tarefa")
            caption.setAlignment(Qt.AlignCenter)
            caption.setObjectName("Caption")
            lay.addWidget(caption)

            lay.addStretch(1)
            self.grid.addWidget(wrap, 0, 0, 1, 2)
            return

        col_count = 2
        row = 0
        col = 0

        for task in self._items:
            card = TaskCard(task)
            # clicked já emite o dict da tarefa
            card.clicked.connect(lambda t, c=card: self._select_card(c, t))

            if self._on_click:
                card.clicked.connect(self._on_click)

            self.grid.addWidget(card, row, col)

            col += 1
            if col >= col_count:
                col = 0
                row += 1

        self.grid.setRowStretch(row + 1, 1)


    def _select_card(self, card: TaskCard, task: Task):
        # remove seleção anterior
        if self._selected_card and self._selected_card is not card:
            if not isValid(self._selected_card):
                self._selected_card = None
            else:
                self._selected_card.setProperty("selected", False)
                self._selected_card.style().unpolish(self._selected_card)
                self._selected_card.style().polish(self._selected_card)
                self._selected_card.update()
        elif self._selected_card and not isValid(self._selected_card):
            self._selected_card = None

        self._selected_card = card
        card.setProperty("selected", True)
        card.style().unpolish(card)
        card.style().polish(card)
        card.update()

        self.task_selected.emit(task)
