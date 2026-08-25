import os
from pathlib import Path
from typing import Dict, List, Any, Optional, Set
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QKeyEvent, QColor, QBrush, QIcon
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QListWidget,
    QListWidgetItem, QLabel, QPushButton, QButtonGroup, QFrame,
    QApplication, QStyle
)
import indexo_core
from app.config.settings_manager import get_db_path
from app.i18n.language_manager import tr, LanguageManager

class SearchPaletteDialog(QDialog):
    folder_selected = Signal(str)  # Emitted when a folder is chosen for organization
    file_selected = Signal(str)    # Emitted when a file is selected

    def __init__(
        self,
        root_dir: Optional[Path] = None,
        last_results: Optional[List[Dict[str, Any]]] = None,
        parent=None
    ):
        super().__init__(parent)
        self.root_dir = root_dir
        self.last_results = last_results or []
        self.current_filter_mode = "all"  # 'all' | 'folders' | 'files'
        
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.resize(720, 520)
        self.init_ui()
        self.populate_initial_suggestions()

    def init_ui(self):
        self.setObjectName("search_palette_dialog")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        # 1. Search Bar Container
        search_card = QFrame()
        search_card.setObjectName("card_options")
        search_card_layout = QHBoxLayout(search_card)
        search_card_layout.setContentsMargins(12, 8, 12, 8)
        search_card_layout.setSpacing(8)

        lbl_icon = QLabel("🔍")
        lbl_icon.setFont(QFont("Segoe UI Emoji", 14))
        search_card_layout.addWidget(lbl_icon)

        self.search_input = QLineEdit()
        self.search_input.setFont(QFont("Inter", 13))
        self.search_input.setPlaceholderText(tr("search.placeholder"))
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setStyleSheet("border: none; background: transparent;")
        self.search_input.textChanged.connect(self.on_query_changed)
        search_card_layout.addWidget(self.search_input, 1)

        btn_close = QPushButton("✕")
        btn_close.setFont(QFont("Inter", 11, QFont.Weight.Bold))
        btn_close.setToolTip("Fechar (Esc)")
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setStyleSheet("padding: 4px 10px; font-weight: bold; border-radius: 4px;")
        btn_close.clicked.connect(self.reject)
        search_card_layout.addWidget(btn_close)

        layout.addWidget(search_card)

        # 2. Filter Buttons (Todos | 📁 Pastas | 📄 Arquivos)
        filter_bar = QHBoxLayout()
        filter_bar.setSpacing(6)

        self.btn_all = QPushButton(tr("palette.filter_all"))
        self.btn_folders = QPushButton(tr("palette.filter_folders"))
        self.btn_files = QPushButton(tr("palette.filter_files"))

        for btn, mode in [(self.btn_all, "all"), (self.btn_folders, "folders"), (self.btn_files, "files")]:
            btn.setCheckable(True)
            btn.setFont(QFont("Inter", 10, QFont.Weight.Medium))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            filter_bar.addWidget(btn)

        self.btn_all.setChecked(True)
        self.filter_group = QButtonGroup(self)
        self.filter_group.addButton(self.btn_all)
        self.filter_group.addButton(self.btn_folders)
        self.filter_group.addButton(self.btn_files)
        self.filter_group.buttonClicked.connect(self.on_filter_changed)

        filter_bar.addStretch()

        self.lbl_count = QLabel("")
        self.lbl_count.setFont(QFont("Inter", 9))
        self.lbl_count.setObjectName("lbl_subtext")
        filter_bar.addWidget(self.lbl_count)

        layout.addLayout(filter_bar)

        # 3. Results List
        self.results_list = QListWidget()
        self.results_list.setFont(QFont("Inter", 10))
        self.results_list.setSpacing(4)
        self.results_list.itemClicked.connect(self.on_item_clicked)
        self.results_list.itemDoubleClicked.connect(self.on_item_clicked)
        layout.addWidget(self.results_list, 1)

        # 4. Keyboard Shortcuts Footer
        footer = QHBoxLayout()
        lbl_hint = QLabel(tr("palette.hint_footer"))
        lbl_hint.setFont(QFont("Inter", 9))
        lbl_hint.setObjectName("lbl_subtext")
        footer.addWidget(lbl_hint)
        footer.addStretch()

        layout.addLayout(footer)

    def on_filter_changed(self, button):
        if button == self.btn_folders:
            self.current_filter_mode = "folders"
        elif button == self.btn_files:
            self.current_filter_mode = "files"
        else:
            self.current_filter_mode = "all"
        self.on_query_changed(self.search_input.text())

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Escape:
            self.reject()
        elif event.key() == Qt.Key.Key_Down:
            curr = self.results_list.currentRow()
            if curr < self.results_list.count() - 1:
                self.results_list.setCurrentRow(curr + 1)
        elif event.key() == Qt.Key.Key_Up:
            curr = self.results_list.currentRow()
            if curr > 0:
                self.results_list.setCurrentRow(curr - 1)
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            item = self.results_list.currentItem()
            if item:
                self.on_item_clicked(item)
        else:
            super().keyPressEvent(event)

    def populate_initial_suggestions(self):
        """Show default user directories and current folder files when search is empty."""
        self.results_list.clear()
        candidates = []

        # 1. User Standard Folders (Always useful for fast organization picking)
        user_home = Path.home()
        standard_dirs = [
            ("Downloads", user_home / "Downloads"),
            ("Documentos", user_home / "Documents"),
            ("Área de Trabalho", user_home / "Desktop"),
            ("Imagens", user_home / "Pictures"),
        ]
        for name, p in standard_dirs:
            if p.exists():
                candidates.append({
                    "type": "folder",
                    "title": f"📁 {name}",
                    "subtitle": str(p),
                    "abs_path": str(p),
                    "badge": "Organizar Pasta" if LanguageManager.get_instance().current_language == "ptBR" else "Organize Folder"
                })

        # 2. Current folder subdirectories
        if self.root_dir and self.root_dir.exists():
            candidates.append({
                "type": "folder",
                "title": f"📂 [Pasta Atual] {self.root_dir.name}",
                "subtitle": str(self.root_dir),
                "abs_path": str(self.root_dir),
                "badge": "Pasta Ativa"
            })
            try:
                for child in list(self.root_dir.iterdir())[:15]:
                    if child.is_dir() and not child.name.startswith((".", "$")):
                        candidates.append({
                            "type": "folder",
                            "title": f"📁 {child.name}",
                            "subtitle": str(child),
                            "abs_path": str(child),
                            "badge": "Organizar Pasta"
                        })
            except Exception:
                pass

        # 3. Current Classified Files
        for it in self.last_results[:20]:
            abs_path = it.get("abs_path", "")
            if abs_path:
                tag = it.get("tag_name") or it.get("category", "")
                name = Path(abs_path).name
                candidates.append({
                    "type": "file",
                    "title": f"📄 {name}",
                    "subtitle": f"[{tag}] {abs_path}" if tag else abs_path,
                    "abs_path": abs_path,
                    "badge": "Visualizar / Fila"
                })

        self.render_candidates(candidates)

    def on_query_changed(self, query: str):
        q = query.strip().lower()
        if not q:
            self.populate_initial_suggestions()
            return

        self.results_list.clear()
        candidates: List[Dict[str, Any]] = []
        seen_paths: Set[str] = set()

        # 1. Search in Active Workspace (Local filesystem search in current_folder)
        if self.root_dir and self.root_dir.exists():
            try:
                # Subfolders matching query
                if self.current_filter_mode in ("all", "folders"):
                    for root, dirs, _ in os.walk(self.root_dir):
                        for d in dirs:
                            if d.startswith((".", "$")):
                                continue
                            if q in d.lower():
                                full_p = str(Path(root) / d)
                                if full_p not in seen_paths:
                                    seen_paths.add(full_p)
                                    candidates.append({
                                        "type": "folder",
                                        "title": f"📁 {d}",
                                        "subtitle": str(Path(root) / d),
                                        "abs_path": full_p,
                                        "badge": "Organizar Pasta"
                                    })
                                if len(candidates) >= 15:
                                    break
                        if len(candidates) >= 15:
                            break

                # Classified and local files matching query
                if self.current_filter_mode in ("all", "files"):
                    for it in self.last_results:
                        abs_p = it.get("abs_path", "")
                        fname = Path(abs_p).name.lower()
                        tag = (it.get("tag_name") or "").lower()
                        cat = (it.get("category") or "").lower()
                        sugg = (it.get("suggested_filename") or "").lower()
                        if q in fname or q in tag or q in cat or q in sugg:
                            if abs_p not in seen_paths:
                                seen_paths.add(abs_p)
                                tag_lbl = it.get("tag_name") or it.get("category") or ""
                                candidates.append({
                                    "type": "file",
                                    "title": f"📄 {Path(abs_p).name}",
                                    "subtitle": f"[{tag_lbl}] {abs_p}" if tag_lbl else abs_p,
                                    "abs_path": abs_p,
                                    "badge": "Visualizar / Fila"
                                })
            except Exception:
                pass

        # 2. Search Full-Text Search (FTS) in Database
        if self.current_filter_mode in ("all", "files"):
            try:
                db_path = str(get_db_path())
                db = indexo_core.PyIndexoDatabase.open(db_path)
                results = db.search_fts(q)
                for r in results:
                    rel = r.get("rel_path", "")
                    tag = r.get("tag", "")
                    snip = r.get("snippet", "")
                    abs_p = str(self.root_dir / rel) if self.root_dir else rel
                    
                    if abs_p not in seen_paths:
                        seen_paths.add(abs_p)
                        tag_lbl = f"[{tag}] " if tag else ""
                        candidates.append({
                            "type": "file",
                            "title": f"📄 {Path(abs_p).name}",
                            "subtitle": f"{tag_lbl}{rel} — {snip[:50]}",
                            "abs_path": abs_p,
                            "badge": "FTS Match"
                        })
            except Exception:
                pass

        # 2.5 Vector Search (Semantic Concept Matching)
        if self.current_filter_mode in ("all", "files") and len(q) >= 3:
            try:
                from app.ai.vector_engine import VectorEngine
                v_engine = VectorEngine.get_instance()
                if v_engine.is_ready and self.last_results:
                    q_vec = v_engine.embed_text(q)
                    if q_vec is not None:
                        for it in self.last_results:
                            abs_p = it.get("abs_path", "")
                            if abs_p and abs_p not in seen_paths:
                                doc_text = f"{Path(abs_p).name} {it.get('category', '')} {it.get('tag_name', '')}"
                                doc_vec = v_engine.embed_text(doc_text)
                                if doc_vec is not None:
                                    sim = v_engine.cosine_similarity(q_vec, doc_vec)
                                    if sim >= 0.40:
                                        seen_paths.add(abs_p)
                                        tag_lbl = it.get("tag_name") or it.get("category") or "Semântico"
                                        candidates.append({
                                            "type": "file",
                                            "title": f"✨ {Path(abs_p).name}",
                                            "subtitle": f"[{tag_lbl}] {abs_p} (Similaridade Semântica)",
                                            "abs_path": abs_p,
                                            "badge": f"Semântica AI {sim * 100:.0f}%"
                                        })
            except Exception as ve:
                pass

        # 3. Direct Path Resolution (if user types an absolute path like C:\...)
        try:
            typed_path = Path(query.strip())
            if typed_path.exists():
                p_str = str(typed_path.resolve())
                if p_str not in seen_paths:
                    is_dir = typed_path.is_dir()
                    candidates.insert(0, {
                        "type": "folder" if is_dir else "file",
                        "title": f"{'📁' if is_dir else '📄'} {typed_path.name or p_str}",
                        "subtitle": p_str,
                        "abs_path": p_str,
                        "badge": "Abrir Pasta" if is_dir else "Abrir Arquivo"
                    })
        except Exception:
            pass

        self.render_candidates(candidates)

    def render_candidates(self, candidates: List[Dict[str, Any]]):
        self.results_list.clear()
        
        filtered = [
            c for c in candidates
            if self.current_filter_mode == "all"
            or (self.current_filter_mode == "folders" and c["type"] == "folder")
            or (self.current_filter_mode == "files" and c["type"] == "file")
        ]

        for c in filtered:
            item = QListWidgetItem()
            item.setText(f"{c['title']}\n  {c['subtitle']}  [{c['badge']}]")
            item.setData(Qt.ItemDataRole.UserRole, c)
            self.results_list.addItem(item)

        total = len(filtered)
        pt = LanguageManager.get_instance().current_language == "ptBR"
        self.lbl_count.setText(f"{total} {'resultado(s)' if pt else 'result(s)'}")

        if self.results_list.count() > 0:
            self.results_list.setCurrentRow(0)

    def on_item_clicked(self, item: QListWidgetItem):
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data:
            return

        abs_path = data.get("abs_path", "")
        item_type = data.get("type", "file")

        if item_type == "folder":
            self.folder_selected.emit(abs_path)
            self.accept()
        else:
            self.file_selected.emit(abs_path)
            self.accept()
