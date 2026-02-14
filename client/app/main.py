from PySide6.QtWidgets import QApplication, QDialog
import sys

from app.db.sqlite import init_db
from app.ui.main_window import MainWindow
from app.ui.dialogs.login_dialog import LoginDialog
from app.core.style import APP_QSS

def main():
    # Garante DB local (criação + seed mínimo)
    init_db()

    app = QApplication(sys.argv)
    app.setStyleSheet(APP_QSS)
    dlg = LoginDialog()
    if dlg.exec() != QDialog.DialogCode.Accepted or not dlg.selected:
        return
    user_id, user_name = dlg.selected
    w = MainWindow(user_id, user_name)
    w.show()
    sys.exit(app.exec())

if __name__=="__main__":
    main()
