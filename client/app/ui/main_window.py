from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QMainWindow, QStackedWidget, QWidget, QHBoxLayout

from app.core.state import AppState

from app.ui.pages.companies import CompaniesPage
from app.ui.pages.home import HomePage
from app.ui.pages.reports import ReportsPage
from app.ui.pages.settings import SettingsPage
from app.ui.components.sidebar import Sidebar


class MainWindow(QMainWindow):
    def __init__(self, user_id: int, user_name: str):
        super().__init__()
        # Título do app (aparece na barra superior do Windows)
        self.setWindowTitle("41 Fiscal Hub")

        # Ícone do app (símbolo) — usado na janela e na taskbar
        icon_path = Path(__file__).resolve().parents[1] / "assets" / "logo_icon.png"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        # Estado compartilhado (ex.: última empresa aberta)
        self.state = AppState()
        self.state.current_user_id = int(user_id)
        self.state.current_user_name = str(user_name)

        # Layout raiz: Sidebar + área principal
        central = QWidget()
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.sidebar = Sidebar()
        self.sidebar.navigate.connect(self._navigate)

        self.stack = QStackedWidget()

        # Páginas
        self.page_companies = CompaniesPage(int(user_id), self.open_company)
        self.page_reports = ReportsPage(int(user_id))
        self.page_settings = SettingsPage(int(user_id), on_created=self._on_created)
        self.page_company_dashboard = HomePage(self.state, self._back_to_companies)

        self._pages = {
            "companies": self.page_companies,
            "reports": self.page_reports,
            "settings": self.page_settings,
            "dashboard": self.page_company_dashboard,
        }

        for key in ("companies", "reports", "settings", "dashboard"):
            self.stack.addWidget(self._pages[key])

        root.addWidget(self.sidebar)
        root.addWidget(self.stack, 1)
        self.setCentralWidget(central)

        # default
        self.sidebar.set_active("companies")
        self.stack.setCurrentWidget(self.page_companies)

    def _navigate(self, key: str):
        if key in ("companies", "reports", "settings"):
            self.sidebar.set_active(key)
            self.stack.setCurrentWidget(self._pages[key])
            if key == "reports":
                self.page_reports.reload()

    def _back_to_companies(self):
        self.sidebar.set_active("companies")
        self.stack.setCurrentWidget(self.page_companies)

    def open_company(self, company_id: int):
        # abre dashboard da empresa
        self.state.selected_company_id = int(company_id)
        self.page_company_dashboard.set_company(company_id)
        # mantém o menu em "Empresas" (faz sentido como fluxo)
        self.sidebar.set_active("companies")
        self.stack.setCurrentWidget(self.page_company_dashboard)

    def _on_created(self, what: str, new_id=None):
        """Callback acionado quando Configurações cria algo.

        `new_id` é opcional (compatibilidade com chamadas antigas/novas).
        """

        # Atualiza listagens/relatórios quando cria via Configurações
        self.page_companies.reload()
        self.page_reports.reload()

        # Se estiver vendo uma empresa específica, recarrega os cards
        if self.stack.currentWidget() == self.page_company_dashboard:
            self.page_company_dashboard.reload_tasks()
