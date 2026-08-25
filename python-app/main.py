import sys
import os
from pathlib import Path
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import QLockFile, QDir
from PySide6.QtGui import QIcon

# Ensure python-app is on sys.path
sys_path = Path(__file__).resolve().parent
if str(sys_path) not in sys.path:
    sys.path.insert(0, str(sys_path))

from app.utils.logger_setup import setup_logger
from app.utils.theme_manager import apply_app_theme, get_app_icon_path
from app.config.settings_manager import (
    get_app_dir, get_data_dir, get_configs_dir, get_db_path, SettingsManager
)
from app.main_window import MainWindow
from app.onboarding.onboarding_wizard import OnboardingWizard
import indexo_core

def main():
    # Set Windows AppUserModelID so taskbar displays dedicated icon
    try:
        import ctypes
        myappid = 'indexo.filemanager.app.v1'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception:
        pass

    app = QApplication(sys.argv)
    app.setApplicationName("Indexo")
    app.setOrganizationName("Indexo")

    # Set Application Icon
    icon_path = get_app_icon_path()
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    # Apply Global Flexoki Theme
    apply_app_theme(app)

    logger = setup_logger()
    logger.info("Starting Indexo on Python {}", sys.version)

    # 1. Single Instance Lock (Section 16.U)
    lock_file_path = get_data_dir() / "indexo.lock"
    lock = QLockFile(str(lock_file_path))
    if not lock.tryLock(100):
        logger.warning("Another instance of Indexo is already running.")
        QMessageBox.warning(
            None,
            "Indexo",
            "O Indexo já está aberto em outra janela.\nNão é permitido abrir duas instâncias simultâneas para proteger seu banco de dados."
        )
        sys.exit(0)

    # 2. Check Read-Only permissions on App Data Dir (Section 14.A)
    try:
        test_file = get_data_dir() / ".test_write"
        test_file.write_text("test")
        test_file.unlink()
    except Exception as e:
        logger.error("Data directory is not writable: {}", e)
        QMessageBox.critical(
            None,
            "Erro de Gravação",
            "Não foi possível salvar dados ao lado do aplicativo.\nVerifique se o disco ou pendrive está protegido contra gravação."
        )
        sys.exit(1)

    # 3. Check SQLite Integrity (Section 16.K)
    db_path = get_db_path()
    try:
        db = indexo_core.PyIndexoDatabase.open(str(db_path))
        if not db.check_integrity():
            logger.error("Database integrity check failed!")
            bak = db_path.with_suffix(".db.bak")
            if bak.exists():
                import shutil
                shutil.copy2(bak, db_path)
                logger.info("Restored database from daily backup.")
                QMessageBox.information(
                    None,
                    "Restauração de Índice",
                    "Seu índice anterior apresentou inconsistências e foi restaurado do backup diário com segurança."
                )
    except Exception as e:
        logger.error("Failed to initialize database: {}", e)

    # 4. Onboarding Wizard on First Execution (Step 1: Welcome -> Step 2: Initial Settings)
    settings_mgr = SettingsManager()
    first_run = settings_mgr.get("first_run", True)

    if first_run:
        wizard = OnboardingWizard()
        wizard.exec()
        settings_mgr.set("first_run", False)

    # 5. Launch Main Window (Step 3: Main Menu Screen)
    window = MainWindow()
    window.show()
    exit_code = app.exec()
    lock.unlock()
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
