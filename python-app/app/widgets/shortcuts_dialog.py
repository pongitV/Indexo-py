from typing import List, Tuple
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea,
    QWidget, QFrame, QPushButton, QGridLayout
)
from app.i18n.language_manager import tr
from app.widgets.smooth_scroll import SmoothScrollArea

class KeyCapWidget(QWidget):
    """Renders a realistic physical keyboard keycap."""
    def __init__(self, key_text: str, parent=None):
        super().__init__(parent)
        self.key_text = key_text
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        lbl = QLabel(key_text)
        lbl.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet("""
            QLabel {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #3A3F4D, stop:1 #232731);
                color: #FFFFFF;
                border: 1px solid #4F5565;
                border-bottom: 3px solid #181A20;
                border-radius: 5px;
                padding: 4px 10px;
                min-width: 24px;
            }
        """)
        layout.addWidget(lbl)


class ShortcutCard(QFrame):
    """Card displaying a shortcut with realistic keyboard keys and description."""
    def __init__(self, keys: List[str], title: str, description: str, parent=None):
        super().__init__(parent)
        self.setObjectName("settings_panel")
        self.setStyleSheet("""
            QFrame {
                border-radius: 8px;
                padding: 10px 14px;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(16)

        # Left: Keyboard Keycaps
        keys_box = QHBoxLayout()
        keys_box.setSpacing(6)
        for i, k in enumerate(keys):
            if i > 0:
                plus = QLabel("+")
                plus.setFont(QFont("Inter", 11, QFont.Weight.Bold))
                plus.setStyleSheet("color: #888;")
                keys_box.addWidget(plus)
            keys_box.addWidget(KeyCapWidget(k))
        layout.addLayout(keys_box)

        # Right: Title and description
        text_box = QVBoxLayout()
        text_box.setSpacing(2)
        
        lbl_title = QLabel(title)
        lbl_title.setFont(QFont("Inter", 10, QFont.Weight.Bold))
        text_box.addWidget(lbl_title)

        lbl_desc = QLabel(description)
        lbl_desc.setFont(QFont("Inter", 9))
        lbl_desc.setStyleSheet("color: #888;")
        text_box.addWidget(lbl_desc)

        layout.addLayout(text_box, 1)


class ShortcutsGuideDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("shortcuts.window_title"))
        self.setMinimumSize(720, 620)
        self.init_ui()

    def init_ui(self):
        is_pt = LanguageManager.get_instance().current_language == "ptBR"
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(16)

        # Header
        header = QHBoxLayout()
        title_box = QVBoxLayout()
        lbl_title = QLabel(tr("shortcuts.title"))
        lbl_title.setFont(QFont("Inter", 14, QFont.Weight.Bold))
        title_box.addWidget(lbl_title)

        lbl_sub = QLabel(tr("shortcuts.desc"))
        lbl_sub.setFont(QFont("Inter", 9))
        lbl_sub.setObjectName("lbl_subtext")
        title_box.addWidget(lbl_sub)

        header.addLayout(title_box, 1)
        main_layout.addLayout(header)

        # Scroll Area for Shortcuts
        self.scroll = SmoothScrollArea()
        self.scroll.setObjectName("settings_scroll")

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        # Section 1: Organização & Navegação
        sec1_title = "Organização & Ações Principais" if is_pt else "Organization & Primary Actions"
        layout.addWidget(self.create_section_label(sec1_title))
        
        layout.addWidget(ShortcutCard(
            ["Ctrl", "O"],
            tr("action.select_folder"),
            "Abre o diálogo para escolher a pasta de trabalho." if is_pt else "Opens dialog to choose working directory."
        ))
        layout.addWidget(ShortcutCard(
            ["Ctrl", "Enter"],
            tr("action.organize_disk"),
            "Move fisicamente os arquivos das pastas permitidas para Indexo_Files." if is_pt else "Moves allowed files physically to Indexo_Files."
        ))
        layout.addWidget(ShortcutCard(
            ["F5"],
            "Recarregar / Atualizar" if is_pt else "Reload / Refresh",
            "Reescaneia todos os arquivos da pasta ativa na hora." if is_pt else "Rescans all files in the active folder immediately."
        ))
        layout.addWidget(ShortcutCard(
            ["Esc"],
            "Fechar Prévia / Voltar" if is_pt else "Close Preview / Back",
            "Fecha o painel lateral de prévia ou retorna do menu." if is_pt else "Closes side preview or returns from menu."
        ))

        # Section 2: Explorador de Arquivos & Árvores
        sec2_title = "Explorador de Arquivos & Árvores" if is_pt else "File Explorer & Trees"
        layout.addWidget(self.create_section_label(sec2_title))
        layout.addWidget(ShortcutCard(
            ["F2"],
            "Renomear Item" if is_pt else "Rename Item",
            "Abre o diálogo para renomear arquivo, pasta ou categoria." if is_pt else "Opens dialog to rename file, folder, or category."
        ))
        layout.addWidget(ShortcutCard(
            ["Delete"],
            "Excluir / Mover para Lixeira" if is_pt else "Delete / Move to Trash",
            "Marca o arquivo selecionado para envio seguro à lixeira." if is_pt else "Marks selected file for safe trash sending."
        ))
        layout.addWidget(ShortcutCard(
            ["Ctrl", "C"],
            "Copiar Caminho" if is_pt else "Copy Path",
            "Copia o caminho completo do arquivo para a área de transferência." if is_pt else "Copies full path to clipboard."
        ))
        layout.addWidget(ShortcutCard(
            ["Duplo Clique" if is_pt else "Double Click"],
            "Abrir Programa Padrão" if is_pt else "Open in Default Program",
            "Abre o arquivo no visualizador ou aplicativo nativo do sistema." if is_pt else "Opens file in the default system viewer."
        ))

        # Section 3: Gestão & Configurações
        sec3_title = "Gestão de Tags & Ajustes" if is_pt else "Tags Management & Settings"
        layout.addWidget(self.create_section_label(sec3_title))
        layout.addWidget(ShortcutCard(
            ["Ctrl", "M"],
            tr("tags.manager_title"),
            "Abre a tela de regras, tags automáticas e manuais do sistema." if is_pt else "Opens system and user tag rules management."
        ))
        layout.addWidget(ShortcutCard(
            ["Ctrl", "K"],
            "Busca Rápida Semântica" if is_pt else "Quick Semantic Search",
            "Busca instantânea com destaque semântico em tempo real." if is_pt else "Instant search with real-time semantic highlighting."
        ))
        layout.addWidget(ShortcutCard(
            ["Ctrl", ","],
            tr("nav.settings"),
            "Abre preferências, tema, idioma e inteligência artificial." if is_pt else "Opens preferences, theme, language, and AI models."
        ))

        layout.addStretch()
        self.scroll.setWidget(container)
        main_layout.addWidget(self.scroll, 1)

        # Bottom close button
        bottom = QHBoxLayout()
        bottom.addStretch()
        btn_close = QPushButton("Entendido" if is_pt else "Got it")
        btn_close.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_close.setStyleSheet("background: #205EA6; color: white; font-weight: bold; padding: 8px 24px; border-radius: 4px; border: none;")
        btn_close.clicked.connect(self.accept)
        bottom.addWidget(btn_close)
        main_layout.addLayout(bottom)

        if self.scroll.verticalScrollBar():
            self.scroll.verticalScrollBar().setValue(0)

    def create_section_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setFont(QFont("Inter", 11, QFont.Weight.Bold))
        lbl.setObjectName("lbl_before")
        return lbl

