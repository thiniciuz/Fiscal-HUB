from __future__ import annotations

from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QLabel, QGraphicsDropShadowEffect, QSizePolicy, QHBoxLayout
)
from PySide6.QtCore import Signal, Qt, QPropertyAnimation, QEasingCurve, QPointF
from PySide6.QtGui import QColor

from app.core.models import Task
from app.core.competencia import fmt_comp
from app.core.lists import STATUS_LABELS


class TaskCard(QFrame):
    """Card clicável de tarefa."""

    clicked = Signal(object)

    def __init__(self, task: Task):
        super().__init__()
        self.task = task

        self.setObjectName("TaskCard")
        # Mantém todos os cards com altura consistente (evita "card maior" quando a grade não está cheia)
        self.setFixedHeight(120)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        # Relevo sutil (Glass Dark)
        self._shadow = QGraphicsDropShadowEffect(self)
        self._shadow.setBlurRadius(18)
        self._shadow.setOffset(0, 4)
        self._shadow.setColor(QColor(0, 0, 0, 120))
        self.setGraphicsEffect(self._shadow)

        # Micro-animações (hover) — bem sutis (100–150ms)
        self._anim_blur = QPropertyAnimation(self._shadow, b"blurRadius", self)
        self._anim_blur.setDuration(140)
        self._anim_blur.setEasingCurve(QEasingCurve.OutCubic)

        self._anim_off = QPropertyAnimation(self._shadow, b"offset", self)
        self._anim_off.setDuration(140)
        self._anim_off.setEasingCurve(QEasingCurve.OutCubic)

        if task.status:
            self.setProperty("status", task.status)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(6)

        title = QLabel(task.titulo)
        title.setObjectName("CardTitle")
        title.setTextInteractionFlags(Qt.NoTextInteraction)
        lay.addWidget(title)

        meta = QHBoxLayout()
        meta.setSpacing(8)

        comp = QLabel(fmt_comp(task.competencia) or "—")
        comp.setObjectName("CardMeta")
        meta.addWidget(comp)

        meta.addStretch(1)

        if task.pdf_blob or task.pdf_path:
            attach = QLabel("📎")
            attach.setObjectName("AttachmentIcon")
            meta.addWidget(attach)

        st = QLabel(STATUS_LABELS.get(task.status, task.status))
        st.setObjectName("StatusChip")
        if task.status:
            st.setProperty("status", task.status)
        meta.addWidget(st)

        lay.addLayout(meta)
        lay.addStretch(1)

    def _animate_shadow(self, blur: float, off_y: float):
        self._anim_blur.stop()
        self._anim_off.stop()

        self._anim_blur.setStartValue(self._shadow.blurRadius())
        self._anim_blur.setEndValue(blur)

        self._anim_off.setStartValue(self._shadow.offset())
        self._anim_off.setEndValue(QPointF(0, off_y))

        self._anim_blur.start()
        self._anim_off.start()

    def enterEvent(self, e):
        # hover
        self._animate_shadow(24, 6)
        return super().enterEvent(e)

    def leaveEvent(self, e):
        # reset
        self._animate_shadow(18, 4)
        return super().leaveEvent(e)

    def mousePressEvent(self, e):
        self.clicked.emit(self.task)
        return super().mousePressEvent(e)
