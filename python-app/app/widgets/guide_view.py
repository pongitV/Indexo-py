"""
Interactive Guide & Documentation View for Indexo.
Provides clear, human-friendly explanations on semantic organization, folder validation,
cohesive bundles, keyboard shortcuts, and safety features in a soft, minimal interface.
"""

from typing import List, Tuple
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QSplitter, QListWidget, QStackedWidget
)
from app.i18n.language_manager import tr, LanguageManager
from app.widgets.smooth_scroll import SmoothScrollArea


class GuideView(QWidget):
    back_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        self.setObjectName("settings_panel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(14)

        # 1. Header with Back button and Title
        header_layout = QHBoxLayout()
        self.btn_back = QPushButton(tr("action.back"))
        self.btn_back.setFont(QFont("Inter", 10, QFont.Weight.Bold))
        self.btn_back.setStyleSheet("padding: 6px 16px; border-radius: 4px;")
        self.btn_back.clicked.connect(self.back_requested.emit)
        header_layout.addWidget(self.btn_back)

        self.lbl_title = QLabel(tr("guide.title", default="Guia de Uso & Conceitos"))
        self.lbl_title.setFont(QFont("Inter", 14, QFont.Weight.Bold))
        header_layout.addWidget(self.lbl_title)

        header_layout.addStretch()
        layout.addLayout(header_layout)

        # 2. Main content Splitter: Left topics list + Right content viewer
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left topics list
        self.topics_list = QListWidget()
        self.topics_list.setFont(QFont("Inter", 10, QFont.Weight.Medium))
        self.topics_list.setMaximumWidth(260)
        self.topics_list.setStyleSheet("""
            QListWidget {
                border: 1px solid rgba(128, 128, 128, 0.2);
                border-radius: 6px;
                padding: 6px;
            }
            QListWidget::item {
                padding: 10px 12px;
                border-radius: 4px;
                margin-bottom: 2px;
            }
            QListWidget::item:selected {
                background: #2563eb;
                color: white;
                font-weight: bold;
            }
        """)

        self.content_stack = QStackedWidget()
        self.rebuild_topics()

        self.topics_list.currentRowChanged.connect(self.content_stack.setCurrentIndex)
        splitter.addWidget(self.topics_list)
        splitter.addWidget(self.content_stack)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)

        layout.addWidget(splitter, 1)

        if self.topics_list.count() > 0:
            self.topics_list.setCurrentRow(0)

    def rebuild_topics(self):
        curr_row = max(0, self.topics_list.currentRow()) if hasattr(self, 'topics_list') else 0
        self.topics_list.clear()

        while self.content_stack.count() > 0:
            w = self.content_stack.widget(0)
            self.content_stack.removeWidget(w)
            w.deleteLater()

        topics = [
            (tr("guide.topic_how_it_works", default="1. Como o Indexo Organiza"), self.create_page_how_it_works),
            (tr("guide.topic_tags_and_categories", default="2. Categorias e Tags Semânticas"), self.create_page_tags_and_categories),
            (tr("guide.topic_folder_validation", default="3. Validação de Pastas e Intrusos"), self.create_page_folder_validation),
            (tr("guide.topic_cohesive_bundles", default="4. Pacotes Coesos (Jogos e Projetos)"), self.create_page_cohesive_bundles),
            (tr("guide.topic_renaming", default="5. Renomeação Padronizada"), self.create_page_renaming),
            (tr("guide.topic_safety_wal", default="6. Segurança e Desfazer em 1 Clique"), self.create_page_safety_wal),
            (tr("guide.topic_shortcuts", default="7. Atalhos de Teclado & Teclas"), self.create_page_shortcuts),
        ]

        for title, page_func in topics:
            self.topics_list.addItem(title)
            self.content_stack.addWidget(page_func())

        if self.topics_list.count() > curr_row:
            self.topics_list.setCurrentRow(curr_row)

    def _wrap_in_scroll(self, widget: QWidget) -> QScrollArea:
        scroll = SmoothScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(widget)
        return scroll

    def _create_card(self, title: str, text: str) -> QFrame:
        card = QFrame()
        card.setObjectName("card_options")
        card.setStyleSheet("QFrame { border: 1px solid rgba(128, 128, 128, 0.15); border-radius: 8px; padding: 14px; margin-bottom: 8px; }")
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(6)

        lbl_t = QLabel(title)
        lbl_t.setFont(QFont("Inter", 11, QFont.Weight.Bold))
        card_layout.addWidget(lbl_t)

        lbl_c = QLabel(text)
        lbl_c.setFont(QFont("Inter", 10))
        lbl_c.setWordWrap(True)
        lbl_c.setStyleSheet("line-height: 1.4;")
        card_layout.addWidget(lbl_c)

        return card

    def _create_keycap_badge(self, keys: list) -> QWidget:
        badge_container = QWidget()
        h = QHBoxLayout(badge_container)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(4)
        h.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        for i, k in enumerate(keys):
            if i > 0:
                lbl_plus = QLabel("+")
                lbl_plus.setFont(QFont("Inter", 10, QFont.Weight.Bold))
                lbl_plus.setStyleSheet("color: #64748b; padding: 0 1px;")
                h.addWidget(lbl_plus)

            key_lbl = QLabel(k)
            key_lbl.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
            key_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            key_lbl.setStyleSheet("""
                QLabel {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ffffff, stop:1 #e2e8f0);
                    color: #0f172a;
                    border: 1px solid #cbd5e1;
                    border-bottom: 2px solid #64748b;
                    border-radius: 5px;
                    padding: 4px 8px;
                    min-width: 26px;
                    font-weight: bold;
                }
            """)
            h.addWidget(key_lbl)

        return badge_container

    def create_page_how_it_works(self) -> QWidget:
        is_pt = LanguageManager.get_instance().current_language == "ptBR"
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 8, 16, 16)
        layout.setSpacing(12)

        lbl_h = QLabel("Como o Indexo Organiza seus Arquivos" if is_pt else "How Indexo Organizes Your Files")
        lbl_h.setFont(QFont("Inter", 13, QFont.Weight.Bold))
        layout.addWidget(lbl_h)

        layout.addWidget(self._create_card(
            "Análise Semântica em Três Níveis" if is_pt else "Three-Tier Semantic Analysis",
            "O Indexo avalia cada arquivo combinando 1. o nome e contexto da pasta atual, 2. o conteúdo interno extraído (como texto de PDFs, documentos e dados de imagens), e 3. o formato e extensão. Isso garante que cada documento seja categorizado pelo seu significado real, e não apenas pela extensão." if is_pt else
            "Indexo evaluates each file by combining 1. the current folder name and context, 2. internally extracted text and image metadata, and 3. format and extensions. This ensures every document is categorized by its actual meaning, not just its extension."
        ))

        layout.addWidget(self._create_card(
            "Visual-First: Você no Controle Total" if is_pt else "Visual-First: You Are in Total Control",
            "Nada é movido ou renomeado sem a sua confirmação. A tela de uso mostra sempre a árvore 'Antes x Depois'. Você pode revisar, alterar qualquer pasta ou descartar com um único clique." if is_pt else
            "Nothing is moved or renamed without your explicit confirmation. The workspace always displays the 'Before x After' tree comparison. You can review, modify any folder, or discard changes with 1 click."
        ))

        layout.addStretch()
        return self._wrap_in_scroll(w)

    def create_page_tags_and_categories(self) -> QWidget:
        is_pt = LanguageManager.get_instance().current_language == "ptBR"
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 8, 16, 16)
        layout.setSpacing(12)

        lbl_h = QLabel("Categorias Físicas e Tags Semânticas" if is_pt else "Physical Categories & Semantic Tags")
        lbl_h.setFont(QFont("Inter", 13, QFont.Weight.Bold))
        layout.addWidget(lbl_h)

        layout.addWidget(self._create_card(
            "O que são Categorias?" if is_pt else "What are Categories?",
            "Categorias definem a estrutura física de pastas onde o arquivo será alocado no seu computador (ex: 'Documentos Fiscais', 'Trabalho', 'Fotos e Imagens'). Cada arquivo pertence a uma pasta de destino clara e limpa." if is_pt else
            "Categories define the physical folder structure where files will be placed on your drive (e.g. 'Financial Documents', 'Work', 'Photos & Images'). Each file belongs to a clean destination folder."
        ))

        layout.addWidget(self._create_card(
            "O que são Tags?" if is_pt else "What are Tags?",
            "Tags são etiquetas temáticas de metadados. Um mesmo arquivo pode ter tags como 'Enel', 'Boleto', 'Comprovante Pago' sem precisar de pastas duplicadas. Você pode buscar por qualquer tag instantaneamente na busca (Ctrl+K)." if is_pt else
            "Tags are metadata labels. The same file can carry tags like 'Invoice', 'Utility Bill', 'Paid Receipt' without needing duplicated physical folders. You can search by tag instantly via Quick Search (Ctrl+K)."
        ))

        layout.addWidget(self._create_card(
            "Gerenciador de Tags & Menu de Contexto (Botão Direito)" if is_pt else "Tag Manager & Right-Click Context Menu",
            "Você pode abrir o 'Gerenciador de Tags' no menu superior a qualquer momento para ver as tags automáticas do Indexo ou criar suas próprias tags manuais. Ao clicar com o botão direito em qualquer arquivo na árvore 'Antes x Depois', você pode aplicar ou trocar a tag e categoria imediatamente!" if is_pt else
            "You can open the 'Tag Manager' from the top bar at any time to review automatic tags or create custom manual tags. Right-clicking any file in the 'Before x After' tree lets you assign or change tags and categories immediately!"
        ))

        layout.addStretch()
        return self._wrap_in_scroll(w)

    def create_page_folder_validation(self) -> QWidget:
        is_pt = LanguageManager.get_instance().current_language == "ptBR"
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 8, 16, 16)
        layout.setSpacing(12)

        lbl_h = QLabel("Validação de Pastas e Detecção de Intrusos" if is_pt else "Folder Validation & Intruder Detection")
        lbl_h.setFont(QFont("Inter", 13, QFont.Weight.Bold))
        layout.addWidget(lbl_h)

        layout.addWidget(self._create_card(
            "Respeito às Pastas que Já Fazem Sentido" if is_pt else "Respecting Folders That Already Make Sense",
            "Se você já possui uma pasta chamada 'Boletos' ou 'Contratos', o Indexo não desfaz a sua organização. Ele lê os arquivos internos, confirma o que realmente pertence ao tema com 96% de certeza e mantém esses arquivos onde estão." if is_pt else
            "If you already have a folder named 'Invoices' or 'Contracts', Indexo respects your established order. It analyzes the internal files, verifies that they match the theme with 96% confidence, and keeps them in place."
        ))

        layout.addWidget(self._create_card(
            "Identificação de Arquivos Intrusos" if is_pt else "Identifying Intruder Files",
            "Se houver arquivos perdidos dentro de uma pasta temática (como uma foto ou instalador solto dentro de 'Boletos'), o Indexo identifica o arquivo como 'Intruso' e sugere movê-lo para a pasta correta (ex: Fotos e Imagens)." if is_pt else
            "If misplaced files exist inside a themed folder (e.g. a stray photo or installer inside 'Invoices'), Indexo identifies the item as an 'Intruder' and recommends moving it to its proper home (e.g. Photos & Images)."
        ))

        layout.addWidget(self._create_card(
            "Pastas Neutras e Caóticas" if is_pt else "Neutral and Cluttered Folders",
            "Pastas de acúmulo temporário como 'Downloads' ou 'Área de Trabalho' são tratadas como neutras. Todos os arquivos são distribuídos automaticamente em suas respectivas categorias limpas." if is_pt else
            "Temporary accumulation folders such as 'Downloads' or 'Desktop' are treated as neutral. All files are automatically distributed into clean target categories."
        ))

        layout.addStretch()
        return self._wrap_in_scroll(w)

    def create_page_cohesive_bundles(self) -> QWidget:
        is_pt = LanguageManager.get_instance().current_language == "ptBR"
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 8, 16, 16)
        layout.setSpacing(12)

        lbl_h = QLabel("Preservação de Pacotes Coesos" if is_pt else "Cohesive Bundle Preservation")
        lbl_h.setFont(QFont("Inter", 13, QFont.Weight.Bold))
        layout.addWidget(lbl_h)

        layout.addWidget(self._create_card(
            "Jogos, Softwares e Projetos de Código" if is_pt else "Games, Software & Code Projects",
            "Programas e jogos dependem de centenas de arquivos interdependentes (.exe, .dll, .pak, assets). O Indexo reconhece essas pastas como 'Pacotes Coesos' e move a pasta inteira em bloco, garantindo que o jogo ou software continue funcionando perfeitamente." if is_pt else
            "Software and games rely on dozens or hundreds of interdependent files (.exe, .dll, .pak, assets). Indexo detects these directories as 'Cohesive Bundles' and moves the entire parent folder intact, preserving full functionality."
        ))

        layout.addWidget(self._create_card(
            "Opções por Pacote" if is_pt else "Per-Bundle Options",
            "Na tela principal de organização, você pode escolher se deseja mover o pacote inteiro, mantê-lo exatamente onde está ou desmembrá-lo individualmente." if is_pt else
            "In the organization view, you can choose whether to move the cohesive parent folder, keep it in place, or disassemble individual files."
        ))

        layout.addStretch()
        return self._wrap_in_scroll(w)

    def create_page_renaming(self) -> QWidget:
        is_pt = LanguageManager.get_instance().current_language == "ptBR"
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 8, 16, 16)
        layout.setSpacing(12)

        lbl_h = QLabel("Padronização e Renomeação Automática" if is_pt else "Standardized Automatic Renaming")
        lbl_h.setFont(QFont("Inter", 13, QFont.Weight.Bold))
        layout.addWidget(lbl_h)

        layout.addWidget(self._create_card(
            "Nomes Claros e Fáceis de Encontrar" if is_pt else "Clean and Discoverable Filenames",
            "O Indexo extrai datas de emissão ou vencimento, nomes de empresas e assuntos para gerar nomes legíveis como '2024-05-10 - Enel - Conta Luz - R$150,00.pdf'." if is_pt else
            "Indexo extracts issue dates, company names, and subjects to generate readable filenames like '2024-05-10 - Enel - Electric Bill - $150.00.pdf'."
        ))

        layout.addWidget(self._create_card(
            "Personalização Completa nas Configurações" if is_pt else "Full Customization in Settings",
            "Na seção de Configurações, você pode escolher o formato da data (AAAA-MM-DD ou DD-MM-AAAA), o separador (' - ', '_', '.') e se prefere nomes em maiúsculas, minúsculas ou capitalizadas." if is_pt else
            "In Settings, you can configure date formats (YYYY-MM-DD or DD-MM-YYYY), separators (' - ', '_', '.'), and letter casing (lowercase, uppercase, title case)."
        ))

        layout.addStretch()
        return self._wrap_in_scroll(w)

    def create_page_safety_wal(self) -> QWidget:
        is_pt = LanguageManager.get_instance().current_language == "ptBR"
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 8, 16, 16)
        layout.setSpacing(12)

        lbl_h = QLabel("Segurança Máxima e Desfazer em 1 Clique" if is_pt else "Maximum Safety & 1-Click Undo")
        lbl_h.setFont(QFont("Inter", 13, QFont.Weight.Bold))
        layout.addWidget(lbl_h)

        layout.addWidget(self._create_card(
            "Registro Atômico (Write-Ahead Log)" if is_pt else "Atomic Write-Ahead Log (WAL)",
            "Toda movimentação realizada no computador é registrada em um diário seguro (.indexo_restore.json). Nada é perdido ou sobrescrito." if is_pt else
            "Every file move and rename on disk is tracked in an atomic journal (.indexo_restore.json). Nothing is overwritten or lost."
        ))

        layout.addWidget(self._create_card(
            "Botão Desfazer" if is_pt else "Undo Button",
            "Se você não gostar do resultado da organização ou quiser voltar atrás, basta clicar em 'Restaurar Última Sessão' para que todos os arquivos retornem exatamente aos seus locais e nomes originais." if is_pt else
            "If you want to revert changes, simply click 'Restore Last Session' to restore all files back to their exact original paths and names."
        ))

        layout.addWidget(self._create_card(
            "Proteção de Duplicados e Lixeira Segura" if is_pt else "Duplicate Protection & Safety Trash",
            "Arquivos duplicados são detectados por hash criptográfico seguro (SHA-256). Ao enviar arquivos para a lixeira, eles são preservados na lixeira segura do aplicativo antes de qualquer exclusão permanente." if is_pt else
            "Duplicate files are detected via cryptographic SHA-256 hashing. Moving files to the trash preserves them in Indexo's safety trash before any permanent deletion."
        ))

        layout.addStretch()
        return self._wrap_in_scroll(w)

    def create_page_shortcuts(self) -> QWidget:
        is_pt = LanguageManager.get_instance().current_language == "ptBR"
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 8, 16, 16)
        layout.setSpacing(10)

        lbl_h = QLabel("Atalhos Rápidos de Teclado & Ações" if is_pt else "Keyboard Shortcuts & Actions")
        lbl_h.setFont(QFont("Inter", 13, QFont.Weight.Bold))
        layout.addWidget(lbl_h)

        if is_pt:
            shortcuts = [
                (["Ctrl", "O"], "Selecionar Pasta", "Abre o seletor para escolher uma nova pasta para organizar."),
                (["Ctrl", "K"], "Busca Rápida Semântica / Paleta", "Pesquisa instantânea de arquivos, tags e comandos."),
                (["Ctrl", "M"], "Gerenciador de Tags & Categorias", "Abre o painel completo de regras, tags automáticas e manuais."),
                (["Ctrl", "Enter"], "Aplicar Organização", "Executa a organização simulada dos arquivos no disco."),
                (["Ctrl", ","], "Configurações do Aplicativo", "Abre o painel de preferências de tema, idioma e renomeação."),
                (["F1"], "Guia de Uso & Documentação", "Abre este guia completo com conceitos e atalhos."),
                (["F2"], "Renomear Item", "Abre diálogo para renomear arquivo ou pasta selecionada na árvore."),
                (["Delete"], "Mover para Lixeira", "Envia o arquivo selecionado para a lixeira segura do Indexo."),
                (["Esc"], "Fechar Prévia / Voltar", "Fecha a barra lateral de prévia ou retorna da tela de ajustes."),
                (["Duplo Clique"], "Abrir Programa Padrão", "Abre o arquivo no visualizador ou aplicativo nativo do sistema."),
            ]
        else:
            shortcuts = [
                (["Ctrl", "O"], "Select Folder", "Opens the folder picker to choose a directory to organize."),
                (["Ctrl", "K"], "Quick Search / Command Palette", "Instant search for files, tags, and commands."),
                (["Ctrl", "M"], "Tag & Category Manager", "Opens the full rules and custom tags management panel."),
                (["Ctrl", "Enter"], "Execute Organization", "Performs simulated file organization on physical disk."),
                (["Ctrl", ","], "Application Settings", "Opens preferences for theme, language, and file renaming."),
                (["F1"], "User Guide & Documentation", "Opens this comprehensive concepts and shortcuts guide."),
                (["F2"], "Rename Item", "Opens dialog to rename selected file or folder in the tree."),
                (["Delete"], "Move to Trash", "Moves selected file to Indexo's safety trash."),
                (["Esc"], "Close Preview / Go Back", "Closes the preview drawer or returns from settings."),
                (["Double Click"], "Open Default App", "Opens the file in the default system viewer or application."),
            ]

        for keys, title, desc in shortcuts:
            card = QFrame()
            card.setObjectName("card_options")
            card.setStyleSheet("QFrame { border: 1px solid rgba(128, 128, 128, 0.15); border-radius: 6px; padding: 10px 14px; }")
            h = QHBoxLayout(card)
            h.setContentsMargins(8, 4, 8, 4)
            h.setSpacing(16)

            badge = self._create_keycap_badge(keys)
            badge.setMinimumWidth(180)
            h.addWidget(badge)

            v = QVBoxLayout()
            v.setSpacing(2)
            lbl_t = QLabel(title)
            lbl_t.setFont(QFont("Inter", 10, QFont.Weight.Bold))
            v.addWidget(lbl_t)
            lbl_d = QLabel(desc)
            lbl_d.setFont(QFont("Inter", 9))
            lbl_d.setStyleSheet("color: #888;")
            v.addWidget(lbl_d)
            h.addLayout(v, 1)

            layout.addWidget(card)

        layout.addStretch()
        return self._wrap_in_scroll(w)

    def retranslate_ui(self):
        self.btn_back.setText(tr("action.back"))
        self.lbl_title.setText(tr("guide.title", default="Guia de Uso & Conceitos"))
        self.rebuild_topics()
