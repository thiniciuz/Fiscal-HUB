from __future__ import annotations

from typing import Dict

from pathlib import Path

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QFrame, QVBoxLayout, QPushButton, QLabel


class Sidebar(QFrame):
    """Menu lateral simples (lista) com expandir/recolher."""

    navigate = Signal(str)  # page key

    def __init__(self):
        super().__init__()
        self.setObjectName("Sidebar")
        self._expanded = True
        self._expanded_w = 220
        self._collapsed_w = 64

        lay = QVBoxLayout(self)
        # Um pouco mais de respiro no topo para acomodar o logo completo
        lay.setContentsMargins(12, 14, 12, 12)
        lay.setSpacing(10)

        # --- Branding (logo completo + ícone) ---
        assets_dir = Path(__file__).resolve().parents[2] / "assets"

        # Logo completo (para sidebar expandida)
        self.brand_full = QLabel()
        self.brand_full.setObjectName("SidebarBrandFull")
        self.brand_full.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        full_path = assets_dir / "logo_full.png"
        if full_path.exists():
            pm = QPixmap(str(full_path))
            # Ajusta largura para caber sem poluir
            pm = pm.scaledToWidth(180, Qt.SmoothTransformation)
            self.brand_full.setPixmap(pm)
        lay.addWidget(self.brand_full, 0, Qt.AlignTop)

        # Ícone (para sidebar recolhida)
        self.brand_icon = QLabel()
        self.brand_icon.setObjectName("SidebarBrandIcon")
        self.brand_icon.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        icon_path = assets_dir / "logo_icon.png"
        if icon_path.exists():
            pm = QPixmap(str(icon_path))
            pm = pm.scaled(QSize(28, 28), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.brand_icon.setPixmap(pm)
        self.brand_icon.hide()
        lay.addWidget(self.brand_icon, 0, Qt.AlignTop)

        # Separador sutil entre logo e menu
        sep = QFrame()
        sep.setObjectName("SidebarSeparator")
        sep.setFixedHeight(1)
        lay.addWidget(sep)

        # Espaço extra para 'descer' o menu um pouco (harmonia visual)
        lay.addSpacing(6)

        self.btn_toggle = QPushButton("≡")
        self.btn_toggle.setObjectName("SidebarToggle")
        self.btn_toggle.clicked.connect(self.toggle)
        lay.addWidget(self.btn_toggle, 0, Qt.AlignTop)

        self._buttons: Dict[str, QPushButton] = {}
        for key, label in (
            ("companies", "Empresas"),
            ("reports", "Relatórios"),
            ("settings", "Configurações"),
        ):
            b = QPushButton(label)
            b.setCheckable(True)
            b.setProperty("role", "nav")
            b.clicked.connect(lambda _, k=key: self.navigate.emit(k))
            self._buttons[key] = b
            lay.addWidget(b)

        lay.addStretch(1)
        self.setFixedWidth(self._expanded_w)

    def set_active(self, key: str):
        for k, b in self._buttons.items():
            b.setChecked(k == key)

    def toggle(self):
        self._expanded = not self._expanded
        self.setFixedWidth(self._expanded_w if self._expanded else self._collapsed_w)

        # Alterna branding (logo completo x ícone)
        if self._expanded:
            self.brand_icon.hide()
            self.brand_full.show()
        else:
            self.brand_full.hide()
            self.brand_icon.show()

        # Quando recolhido, mostra só "•" para manter click targets
        for _, b in self._buttons.items():
            if self._expanded:
                full = b.property("fullText") or b.text()
                b.setText(str(full))
            else:
                if not b.property("fullText"):
                    b.setProperty("fullText", b.text())
                b.setText("•")
