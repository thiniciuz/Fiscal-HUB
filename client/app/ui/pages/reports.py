from __future__ import annotations

from typing import Dict, Optional, List

from PySide6.QtCore import Qt, QRectF, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QGraphicsDropShadowEffect, QPushButton, QScrollArea, QSizePolicy, QMessageBox,
)

# QtCharts pode não estar disponível em alguns ambientes (ex.: PySide6_Essentials apenas).
# Neste caso, usamos um gráfico rosquinha desenhado via QPainter (sem dependências extras).
try:
    from PySide6.QtCharts import QChart, QChartView, QPieSeries
    _HAS_CHARTS = True
except Exception:  # pragma: no cover
    _HAS_CHARTS = False

from app.core.lists import STATUS_ORDER, STATUS_LABELS
from app.core.theme import STATUS_COLORS, BASE
from app.core.competencia import fmt_comp
from app.db.repositories import TaskRepository
from app.core.attachments import open_with_default_app, resolve_pdf_path, write_pdf_blob_to_temp


class DonutChartWidget(QWidget):
    """Gráfico rosquinha leve (fallback) usando QPainter, sem QtCharts."""

    status_clicked = Signal(str)

    def __init__(self):
        super().__init__()
        self._data: Dict[str, int] = {s: 0 for s in STATUS_ORDER}
        self.setMinimumHeight(320)
        # lista de segmentos calculados para clique: (status, start_deg, end_deg)
        self._segments: List[tuple] = []

    def set_data(self, data: Dict[str, int]) -> None:
        self._data = {s: int(data.get(s, 0)) for s in STATUS_ORDER}
        self._rebuild_segments()
        self.update()

    def _rebuild_segments(self) -> None:
        total = sum(self._data.values())
        segs: List[tuple] = []
        if total <= 0:
            self._segments = segs
            return
        # 0° = topo (12h), sentido horário.
        start = 0.0
        for st in STATUS_ORDER:
            v = int(self._data.get(st, 0))
            if v <= 0:
                continue
            frac = v / total
            end = start + (360.0 * frac)
            segs.append((st, start, end))
            start = end
        self._segments = segs

    def mousePressEvent(self, event):  # noqa: N802
        # Detecta clique em uma fatia para drill-down
        total = sum(self._data.values())
        if total <= 0:
            return

        w = self.width()
        h = self.height()
        cx = w / 2.0
        cy = h / 2.0

        dx = event.position().x() - cx
        dy = event.position().y() - cy
        dist2 = (dx * dx) + (dy * dy)

        margin = 18
        size = max(10, min(w, h) - (margin * 2))
        r_outer = size / 2.0
        ring = max(12, int(size * 0.18))
        r_inner = max(0.0, r_outer - ring)

        if dist2 < (r_inner * r_inner) or dist2 > (r_outer * r_outer):
            return

        # Converte para ângulo (0° = topo, sentido horário)
        import math

        ang = math.degrees(math.atan2(dy, dx))  # 0° no eixo X
        ang = (ang + 90.0) % 360.0

        for st, a0, a1 in self._segments:
            if a0 <= ang < a1:
                self.status_clicked.emit(str(st))
                return

    def paintEvent(self, event):  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()

        # Área do círculo
        margin = 18
        size = max(10, min(w, h) - (margin * 2))
        rect = QRectF((w - size) / 2, (h - size) / 2, size, size)

        total = sum(self._data.values())

        # Espessura do anel
        ring = max(12, int(size * 0.18))

        if total <= 0:
            # Anel neutro + texto
            pen = QPen(QColor("#334155"), ring)
            pen.setCapStyle(Qt.RoundCap)
            painter.setPen(pen)
            painter.drawArc(rect, 0, 360 * 16)

            painter.setPen(QColor("#9AA7C1"))
            painter.drawText(self.rect(), Qt.AlignCenter, "Sem tarefas")
            return

        # Começa no topo (12h) e desenha no sentido horário (span negativo)
        start = 90 * 16
        for st in STATUS_ORDER:
            v = int(self._data.get(st, 0))
            if v <= 0:
                continue
            span = int(-360 * 16 * (v / total))
            pen = QPen(QColor(STATUS_COLORS.get(st, "#64748B")), ring)
            pen.setCapStyle(Qt.FlatCap)
            painter.setPen(pen)
            painter.drawArc(rect, start, span)
            start += span

        # Texto central (total)
        painter.setPen(QColor("#EAF0FF"))
        painter.drawText(self.rect(), Qt.AlignCenter, str(total))


class ReportsPage(QWidget):
    """Relatórios: gráfico de status (todas as empresas)."""

    def __init__(self, user_id: int):
        super().__init__()
        self.repo = TaskRepository(int(user_id))

        self._selected_status: Optional[str] = None
        self._selected_company_id: Optional[int] = None

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)

        title = QLabel("Relatórios")
        title.setObjectName("H0")
        root.addWidget(title)

        self.card = QFrame()
        self.card.setObjectName("Card")
        card_lay = QVBoxLayout(self.card)
        card_lay.setContentsMargins(14, 14, 14, 14)
        card_lay.setSpacing(10)

        self.subtitle = QLabel("Status das tarefas (todas as empresas)")
        self.subtitle.setObjectName("H2")
        card_lay.addWidget(self.subtitle)

        body = QHBoxLayout()
        body.setSpacing(12)
        card_lay.addLayout(body, 1)

        # Chart
        if _HAS_CHARTS:
            self.series = QPieSeries()
            # Rosquinha mais "espessa" + levemente menor (pedido do layout)
            self.series.setHoleSize(0.50)
            self.series.setPieSize(0.78)

            self.chart = QChart()
            self.chart.addSeries(self.series)
            self.chart.legend().setVisible(True)
            self.chart.legend().setAlignment(Qt.AlignRight)
            # Aumenta um pouco a fonte dos status (legenda) para melhor leitura no tema Glass Dark
            _f = self.chart.legend().font()
            _f.setPointSize(max(9, _f.pointSize() + 1))
            self.chart.legend().setFont(_f)
            self.chart.setBackgroundVisible(False)
            self.chart.setTitle("")

            self.view = QChartView(self.chart)
            self.view.setRenderHint(QPainter.Antialiasing)
            self.view.setMinimumHeight(320)
            # "Relevo" sutil
            fx = QGraphicsDropShadowEffect(self.view)
            fx.setBlurRadius(28)
            fx.setOffset(0, 6)
            fx.setColor(QColor(0, 0, 0, 140))
            self.view.setGraphicsEffect(fx)
            body.addWidget(self.view, 1)

            # Drill-down (QtCharts)
            self.series.hovered.connect(lambda *_: None)
        else:
            # Fallback: rosquinha desenhada via QPainter (sem QtCharts)
            self.view = DonutChartWidget()
            fx = QGraphicsDropShadowEffect(self.view)
            fx.setBlurRadius(28)
            fx.setOffset(0, 6)
            fx.setColor(QColor(0, 0, 0, 140))
            self.view.setGraphicsEffect(fx)
            body.addWidget(self.view, 1)
            self.view.status_clicked.connect(self._on_status_clicked)

        # Painel direito (drill-down)
        self.side = QFrame()
        # SidePanel usa estilo "glass" contínuo (sem aparência de remendo)
        self.side.setObjectName("SidePanel")
        self.side.setMinimumWidth(320)
        self.side_lay = QVBoxLayout(self.side)
        self.side_lay.setContentsMargins(12, 12, 12, 12)
        self.side_lay.setSpacing(10)

        self.side_title = QLabel("Clique em um status")
        self.side_title.setObjectName("H2")
        self.side_lay.addWidget(self.side_title)

        self.side_hint = QLabel("Selecione uma fatia do gráfico para ver empresas e tarefas.")
        self.side_hint.setObjectName("Caption")
        self.side_hint.setWordWrap(True)
        self.side_lay.addWidget(self.side_hint)

        self.btn_back_level = QPushButton("← Voltar")
        self.btn_back_level.setVisible(False)
        self.btn_back_level.clicked.connect(self._back_level)
        self.side_lay.addWidget(self.btn_back_level)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll_content = QFrame()
        self.scroll_lay = QVBoxLayout(self.scroll_content)
        self.scroll_lay.setContentsMargins(0, 0, 0, 0)
        self.scroll_lay.setSpacing(6)
        self.scroll.setWidget(self.scroll_content)
        self.side_lay.addWidget(self.scroll, 1)

        body.addWidget(self.side, 0)

        # Observação: removemos o "resumo" textual lateral para deixar o layout mais limpo.

        root.addWidget(self.card, 1)

        self.reload()

    def reload(self):
        counts = self.repo.count_by_status()  # status -> count

        # Always show all statuses (even if 0)
        full: Dict[str, int] = {s: int(counts.get(s, 0)) for s in STATUS_ORDER}
        total = sum(full.values())

        # Chart update
        if not _HAS_CHARTS:
            # type: ignore[attr-defined] - QWidget fallback possui set_data
            self.view.set_data(full)  # pyright: ignore
            return

        self.series.clear()
        # Mantém mapeamento de fatia -> status
        self._slice_to_status: Dict[object, str] = {}
        for st in STATUS_ORDER:
            v = full[st]
            if v <= 0:
                continue
            sl = self.series.append(f"{STATUS_LABELS[st]} ({v})", v)
            self._slice_to_status[sl] = st
            sl.setBrush(QColor(STATUS_COLORS[st]))
            # borda/"gap" e relevo leve entre as fatias
            sl.setPen(QPen(QColor(BASE["panel"]), 2))
            sl.setExploded(True)
            sl.setExplodeDistanceFactor(0.025)
            sl.setLabelVisible(False)

            # Drill-down
            try:
                sl.clicked.connect(lambda _=False, s=st: self._on_status_clicked(s))  # type: ignore[attr-defined]
            except Exception:
                pass

        # If empty, show a single neutral slice
        if self.series.count() == 0:
            sl = self.series.append("Sem tarefas", 1)
            sl.setLabelVisible(False)
            sl.setBrush(QColor("#334155"))
            sl.setPen(QPen(QColor(BASE["panel"]), 2))

    def _clear_side_list(self) -> None:
        while self.scroll_lay.count():
            it = self.scroll_lay.takeAt(0)
            w = it.widget()
            if w:
                w.deleteLater()
        self.scroll_lay.addStretch(1)

    def _on_status_clicked(self, status: str) -> None:
        self._selected_status = str(status)
        self._selected_company_id = None

        self.btn_back_level.setVisible(False)
        self.side_title.setText(f"{STATUS_LABELS.get(status, status)} → Empresas")
        self.side_hint.setText("Clique em uma empresa para ver as tarefas.")

        items = self.repo.companies_with_status(status)
        self._clear_side_list()
        # remove stretch inserted by _clear_side_list and rebuild
        while self.scroll_lay.count():
            it = self.scroll_lay.takeAt(0)
            w = it.widget()
            if w:
                w.deleteLater()

        if not items:
            lb = QLabel("Nenhuma empresa nesse status.")
            lb.setObjectName("Muted")
            self.scroll_lay.addWidget(lb)
            self.scroll_lay.addStretch(1)
            return

        for row in items:
            cid = int(row["id"])  # type: ignore[index]
            nome = str(row["nome"])  # type: ignore[index]
            qtd = int(row["qtd"])  # type: ignore[index]
            b = QPushButton(f"{nome}  •  {qtd}")
            b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            b.clicked.connect(lambda _=False, c=cid: self._on_company_clicked(c))
            self.scroll_lay.addWidget(b)
        self.scroll_lay.addStretch(1)

    def _on_company_clicked(self, company_id: int) -> None:
        if not self._selected_status:
            return
        self._selected_company_id = int(company_id)

        self.btn_back_level.setVisible(True)
        self.side_title.setText("Tarefas")
        self.side_hint.setText("Tarefas filtradas por empresa e status.")

        tasks = self.repo.tasks_by_company_and_status(company_id, self._selected_status)

        while self.scroll_lay.count():
            it = self.scroll_lay.takeAt(0)
            w = it.widget()
            if w:
                w.deleteLater()

        if not tasks:
            lb = QLabel("Nenhuma tarefa.")
            lb.setObjectName("Muted")
            self.scroll_lay.addWidget(lb)
            self.scroll_lay.addStretch(1)
            return

        for t in tasks:
            comp = fmt_comp(t.competencia) or "—"

            wrap = QFrame()
            wrap.setObjectName("Card")
            wrap_lay = QHBoxLayout(wrap)
            wrap_lay.setContentsMargins(10, 8, 10, 8)
            wrap_lay.setSpacing(8)

            text = QLabel(f"{t.titulo}\nCompetência: {comp}")
            text.setWordWrap(True)
            wrap_lay.addWidget(text, 1)

            if t.pdf_blob or t.pdf_path:
                btn = QPushButton("📎")
                btn.setProperty("role", "secondary")
                btn.setFixedWidth(32)
                btn.setToolTip("Abrir PDF")
                btn.clicked.connect(lambda _=False, task=t: self._open_task_pdf(task))
                wrap_lay.addWidget(btn)

            self.scroll_lay.addWidget(wrap)
        self.scroll_lay.addStretch(1)

    def _back_level(self) -> None:
        # Volta de tarefas -> empresas (mantém status selecionado)
        if self._selected_status:
            self._on_status_clicked(self._selected_status)

    def _open_task_pdf(self, task) -> None:
        try:
            if task.pdf_blob:
                data = task.pdf_blob
                if isinstance(data, memoryview):
                    data = data.tobytes()
                name = task.pdf_path or f"task_{task.id}.pdf"
                p = write_pdf_blob_to_temp(data, name)
                open_with_default_app(str(p))
            elif task.pdf_path:
                p = resolve_pdf_path(task.pdf_path)
                if not p.exists():
                    raise FileNotFoundError(f"PDF não encontrado: {p}")
                open_with_default_app(str(p))
        except Exception as e:
            QMessageBox.warning(self, "PDF", str(e))
