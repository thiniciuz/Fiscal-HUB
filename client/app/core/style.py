from __future__ import annotations

from app.core.theme import BASE, STATUS_COLORS

APP_QSS = f"""
QWidget {{
  background: {BASE['bg']};
  color: {BASE['text']};
  font-size: 13px;
}}

/* Importante: evita "remendos" (labels/heranças com fundo sólido). */
QLabel {{
  background: transparent;
}}

QLabel#Accent {{
  color: {BASE['accent']};
}}
QLabel#Muted {{
  color: {BASE['muted']};
}}
QLabel#H0 {{
  font-size: 22px;
  font-weight: 700;
}}
QLabel#H1 {{
  font-size: 18px;
  font-weight: 700;
}}

/* Hierarquia tipográfica (Glass Dark) */
QLabel#H2 {{
  font-size: 15px;
  font-weight: 600;
  color: rgba(234, 240, 255, 0.90);
}}
QLabel#Caption {{
  font-size: 12px;
  color: rgba(154, 167, 193, 0.85);
}}

/* Cards/painéis */
QFrame#Card {{
  /* Glass dark: painel semi-transparente com leve gradiente */
  background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
    stop:0 rgba(255,255,255,0.06),
    stop:1 rgba(0,0,0,0.18)
  );
  background-color: rgba(12, 18, 34, 0.55);
  border: 1px solid rgba(255,255,255,0.06);
  border-radius: 14px;
}}

/* Feedback de interação (hover) para "cards" */
QFrame#Card:hover {{
  border: 1px solid rgba(59, 130, 246, 0.20);
}}

/* Painel lateral de drill-down (evita "remendo": sem moldura completa, só divisória) */
QFrame#SidePanel {{
  background: rgba(12, 18, 34, 0.35);
  border: none;
  border-left: 1px solid rgba(255,255,255,0.06);
  border-radius: 14px;
}}

/* Sidebar */
QFrame#Sidebar {{
  background: {BASE['panel']};
  border-right: 1px solid {BASE['border']};
}}

QFrame#SidebarSeparator {{
  background: rgba(255,255,255,0.06);
}}

QPushButton#SidebarToggle {{
  padding: 6px 8px;
  border-radius: 12px;
  border: 1px solid rgba(255,255,255,0.10);
  background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
    stop:0 rgba(255,255,255,0.08),
    stop:1 rgba(0,0,0,0.18)
  );
}}
QPushButton#SidebarToggle:hover {{
  border: 1px solid rgba(59, 130, 246, 0.55);
}}

QPushButton[role="nav"] {{
  text-align: left;
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid transparent;
  background: transparent;
}}
QPushButton[role="nav"]:hover {{
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.06);
}}
QPushButton[role="nav"]:checked {{
  /* Estado ativo com "indicador" lateral */
  background: rgba(59, 130, 246, 0.14);
  border: 1px solid rgba(59, 130, 246, 0.35);
  border-left: 3px solid rgba(59, 130, 246, 0.95);
  padding-left: 10px;
}}
QPushButton[role="nav"]:pressed {{
  background: rgba(255,255,255,0.05);
}}

/* Botões padrão */
QPushButton {{
  padding: 8px 12px;
  border-radius: 10px;
  border: 1px solid {BASE['border']};
  background: {BASE['chip']};
}}
QPushButton:hover {{
  border: 1px solid rgba(59, 130, 246, 0.55);
}}
QPushButton:pressed {{
  background: rgba(255,255,255,0.06);
  border: 1px solid rgba(59, 130, 246, 0.25);
}}
QPushButton:checked {{
  background: rgba(59, 130, 246, 0.20);
  border: 1px solid rgba(59, 130, 246, 0.55);
}}
QPushButton:disabled {{
  color: {BASE['muted']};
}}

/* Chips (filtros como Regime em Empresas) */
QPushButton[role="chip"] {{
  padding: 6px 12px;
  border-radius: 12px;
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.10);
}}
QPushButton[role="chip"]:hover {{
  border: 1px solid rgba(59, 130, 246, 0.55);
}}
QPushButton[role="chip"]:pressed {{
  background: rgba(255,255,255,0.06);
  border: 1px solid rgba(59, 130, 246, 0.35);
}}
QPushButton[role="chip"]:checked {{
  background: rgba(59, 130, 246, 0.18);
  border: 1px solid rgba(59, 130, 246, 0.65);
}}

/* Botões de status */
QPushButton[role="status"] {{
  padding: 6px 10px;
}}
QPushButton[role="status"][status="PENDENTE"] {{
  background: rgba(239, 68, 68, 0.16);
}}
QPushButton[role="status"][status="EM_ANDAMENTO"] {{
  background: rgba(245, 158, 11, 0.16);
}}
QPushButton[role="status"][status="CONCLUIDA"] {{
  background: rgba(34, 197, 94, 0.16);
}}
QPushButton[role="status"][status="ENVIADA"] {{
  background: rgba(59, 130, 246, 0.16);
}}
QPushButton[role="status"]:checked {{
  border: 1px solid rgba(255,255,255,0.14);
}}

/* Inputs (inclui QSpinBox) */
QLineEdit, QComboBox, QSpinBox {{
  padding: 6px 10px;
  border-radius: 10px;
  border: 1px solid {BASE['border']};
  background: rgba(10, 16, 32, 0.65);
}}
QLineEdit:hover, QComboBox:hover, QSpinBox:hover {{
  border: 1px solid rgba(59, 130, 246, 0.35);
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{
  border: 1px solid rgba(59, 130, 246, 0.75);
}}
QComboBox QAbstractItemView {{
  background: {BASE['panel']};
  border: 1px solid {BASE['border']};
  selection-background-color: rgba(59, 130, 246, 0.20);
}}

/* Tabela */
QTableWidget {{
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 12px;
  background: rgba(10, 16, 32, 0.65);
  /* Zebra sutil no dark mode */
  alternate-background-color: rgba(255,255,255,0.03);
}}
QHeaderView::section {{
  background: rgba(12, 18, 34, 0.55);
  color: rgba(234, 240, 255, 0.85);
  padding: 8px 10px;
  border: none;
}}
QTableCornerButton::section {{
  background: rgba(12, 18, 34, 0.55);
  border: none;
}}
QTableWidget::item {{
  padding: 10px;
  border: none;
  /* Fundo transparente para zebra vir do viewport */
  background: transparent;
}}
QTableWidget::item:alternate {{
  background: rgba(255,255,255,0.03);
}}
QTableWidget::item:selected {{
  background: rgba(59, 130, 246, 0.20);
  outline: none;
}}
QTableWidget:focus {{
  outline: none;
}}

/* Task card */
QFrame#TaskCard {{
  background: rgba(10, 16, 32, 0.65);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 12px;
}}
QFrame#TaskCard:hover {{
  border: 1px solid rgba(59, 130, 246, 0.55);
}}
QFrame#TaskCard[status="PENDENTE"] {{
  border-left: 4px solid {STATUS_COLORS['PENDENTE']};
}}
QFrame#TaskCard[status="EM_ANDAMENTO"] {{
  border-left: 4px solid {STATUS_COLORS['EM_ANDAMENTO']};
}}
QFrame#TaskCard[status="CONCLUIDA"] {{
  border-left: 4px solid {STATUS_COLORS['CONCLUIDA']};
}}
QFrame#TaskCard[status="ENVIADA"] {{
  border-left: 4px solid {STATUS_COLORS['ENVIADA']};
}}

/* Scrollbar discreta */
QScrollBar:vertical {{
  background: transparent;
  width: 10px;
  margin: 0px;
}}
QScrollBar::handle:vertical {{
  background: rgba(255,255,255,0.14);
  border-radius: 5px;
  min-height: 20px;
}}
QScrollBar::handle:vertical:hover {{
  background: rgba(255,255,255,0.20);
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
  height: 0px;
}}
"""
