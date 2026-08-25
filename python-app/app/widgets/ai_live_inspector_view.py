"""
Live AI Reasoning & Thought Stream Inspector View for Indexo.
Displays the step-by-step thinking process, extraction snippets, vector similarity,
and structured JSON decision making of local AI for each file in the selected folder.
"""

import json
import time
from pathlib import Path
from typing import Dict, List, Any, Optional

from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtGui import QFont, QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSplitter, QFrame, QListWidget, QListWidgetItem, QTextEdit,
    QLineEdit, QProgressBar, QSizePolicy, QScrollArea
)

from app.i18n.language_manager import tr, LanguageManager
from app.config.settings_manager import SettingsManager
from app.ai.model_manager import ModelManager
from app.ai.ai_tester import AITester, AITestDiagnosis
from app.classification.entity_regex import generate_standard_filename
from app.widgets.smooth_scroll import SmoothScrollArea


class AILiveInspectorWorker(QThread):
    """Background worker that streams step-by-step reasoning for each file."""
    file_analysis_started = Signal(str, int, int)      # filename, index, total
    file_thought_updated = Signal(dict)                # detailed thought payload
    analysis_finished = Signal(int)                    # total analyzed

    def __init__(self, items: List[Dict[str, Any]], parent=None):
        super().__init__(parent)
        self.items = items
        self.is_cancelled = False

    def cancel(self):
        self.is_cancelled = True

    def run(self):
        tester = AITester()
        total = len(self.items)

        for idx, it in enumerate(self.items):
            if self.is_cancelled:
                break

            rel_path = it.get("rel_path") or Path(it.get("abs_path", "")).name
            self.file_analysis_started.emit(rel_path, idx + 1, total)

            start_t = time.perf_counter()
            query_text = f"{rel_path} {it.get('extracted_text', '')[:300]}"
            diag: AITestDiagnosis = tester.diagnose_query(query_text)
            elapsed_ms = (time.perf_counter() - start_t) * 1000.0

            # Synthesize realistic, transparent thought breakdown
            ext = it.get("extension") or Path(rel_path).suffix
            size = it.get("size", 0)
            extracted = it.get("extracted_text") or "(Sem texto extraído ou arquivo binário/imagem)"

            thought_payload = {
                "rel_path": rel_path,
                "abs_path": it.get("abs_path", ""),
                "size": size,
                "ext": ext,
                "categoria": diag.categoria,
                "subcategoria": diag.subcategoria,
                "tags": diag.tags,
                "confianca": diag.confianca,
                "engine_label": diag.engine_label,
                "elapsed_ms": elapsed_ms,
                "resumo": diag.reasoning,
                "extracted_snippet": extracted[:400],
                "proposed_name": it.get("suggested_filename") or rel_path,
                "steps": [
                    f"1. 📥 Metadados lidos: Extensão {ext}, Tamanho {size / 1024:.1f} KB.",
                    f"2. 🔍 Extração de Texto: {len(extracted)} caracteres analisados.",
                    f"3. 🧠 Motor de Inferência: {diag.engine_label} acionado.",
                    f"4. 🎯 Similaridade / Regra: Categoria '{diag.categoria}' com {diag.confianca * 100:.1f}% de certeza.",
                    f"5. 📐 Padronização: Destino sugerido em '{diag.categoria}/{diag.subcategoria or 'Geral'}'.",
                ],
                "raw_decision": {
                    "categoria": diag.categoria,
                    "subcategoria": diag.subcategoria,
                    "tags": diag.tags,
                    "confianca": round(diag.confianca, 3),
                    "motor": diag.engine_label,
                    "tempo_ms": round(elapsed_ms, 2),
                    "resumo": diag.reasoning,
                }
            }

            self.file_thought_updated.emit(thought_payload)
            time.sleep(0.05)  # Smooth UI update pace

        self.analysis_finished.emit(total)


class AILiveInspectorView(QWidget):
    """
    Dedicated view that exposes the local AI live thought process,
    reasoning chain, and prompt/response details for every file.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings_mgr = SettingsManager()
        self.current_items: List[Dict[str, Any]] = []
        self.thoughts_cache: Dict[str, Dict[str, Any]] = {}
        self.worker: Optional[AILiveInspectorWorker] = None

        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # 1. Header Card with Engine Info & Actions
        header_card = QFrame()
        header_card.setObjectName("card_options")
        header_card.setStyleSheet("QFrame#card_options { border-radius: 8px; padding: 12px; }")
        hl = QVBoxLayout(header_card)
        hl.setContentsMargins(14, 12, 14, 12)
        hl.setSpacing(8)

        top_row = QHBoxLayout()
        self.lbl_title = QLabel(f"🧠 {tr('ai_live.title')}")
        self.lbl_title.setFont(QFont("Inter", 13, QFont.Weight.Bold))
        top_row.addWidget(self.lbl_title, 1)

        self.lbl_engine_badge = QLabel("⚡ Motor Ativo: Tier 1 (Rust) + Tier 2 (ONNX Vetorial)")
        self.lbl_engine_badge.setFont(QFont("Inter", 9, QFont.Weight.Bold))
        self.lbl_engine_badge.setStyleSheet("background: #0284c722; color: #0284c7; border: 1px solid #0284c7; border-radius: 12px; padding: 3px 10px;")
        top_row.addWidget(self.lbl_engine_badge)

        hl.addLayout(top_row)

        self.lbl_subtitle = QLabel(tr("ai_live.subtitle"))
        self.lbl_subtitle.setObjectName("lbl_subtext")
        self.lbl_subtitle.setFont(QFont("Inter", 9))
        self.lbl_subtitle.setWordWrap(True)
        hl.addWidget(self.lbl_subtitle)

        # Action Button Row
        btn_row = QHBoxLayout()
        self.btn_analyze_all = QPushButton(tr("ai_live.btn_analyze_all"))
        self.btn_analyze_all.setFont(QFont("Inter", 10, QFont.Weight.Bold))
        self.btn_analyze_all.setStyleSheet("background: #2563eb; color: white; padding: 6px 14px; border-radius: 6px; border: none;")
        self.btn_analyze_all.clicked.connect(self.start_live_analysis)
        btn_row.addWidget(self.btn_analyze_all)

        self.btn_stop = QPushButton(tr("ai_live.btn_stop"))
        self.btn_stop.setFont(QFont("Inter", 10))
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.stop_live_analysis)
        btn_row.addWidget(self.btn_stop)

        self.search_filter = QLineEdit()
        self.search_filter.setFont(QFont("Inter", 9))
        self.search_filter.setPlaceholderText(tr("search.placeholder"))
        self.search_filter.textChanged.connect(self.filter_file_list)
        btn_row.addWidget(self.search_filter, 1)

        hl.addLayout(btn_row)

        # Live Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedHeight(12)
        hl.addWidget(self.progress_bar)

        main_layout.addWidget(header_card)

        # 2. Main Content Splitter (Left: File List, Right: Thought Stream Panel)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left Column: File List
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)

        self.lbl_files_header = QLabel("Arquivos Analisados:")
        self.lbl_files_header.setFont(QFont("Inter", 10, QFont.Weight.Bold))
        left_layout.addWidget(self.lbl_files_header)

        self.file_list = QListWidget()
        self.file_list.setFont(QFont("Inter", 9))
        self.file_list.currentItemChanged.connect(self.on_file_selected)
        left_layout.addWidget(self.file_list, 1)

        splitter.addWidget(left_widget)

        # Right Column: Detailed Thought Panel (Inside SmoothScrollArea)
        right_scroll = SmoothScrollArea()
        right_scroll.setWidgetResizable(True)
        right_content = QWidget()
        self.thought_layout = QVBoxLayout(right_content)
        self.thought_layout.setContentsMargins(12, 12, 12, 12)
        self.thought_layout.setSpacing(10)

        # Card A: Overview & Metrics
        self.metrics_card = QFrame()
        self.metrics_card.setObjectName("card_options")
        mc_layout = QVBoxLayout(self.metrics_card)
        self.lbl_thought_file = QLabel("📄 Selecione um arquivo")
        self.lbl_thought_file.setFont(QFont("Inter", 12, QFont.Weight.Bold))
        mc_layout.addWidget(self.lbl_thought_file)

        self.lbl_thought_summary = QLabel(tr("ai_live.select_file_hint"))
        self.lbl_thought_summary.setFont(QFont("Inter", 9))
        self.lbl_thought_summary.setWordWrap(True)
        mc_layout.addWidget(self.lbl_thought_summary)

        self.thought_layout.addWidget(self.metrics_card)

        # Card B: Extraction Snippet
        self.extract_card = QFrame()
        self.extract_card.setObjectName("card_options")
        ec_layout = QVBoxLayout(self.extract_card)
        self.lbl_ext_head = QLabel("🔍 " + tr("ai_live.step_extract"))
        self.lbl_ext_head.setFont(QFont("Inter", 10, QFont.Weight.Bold))
        ec_layout.addWidget(self.lbl_ext_head)

        self.txt_extract_snippet = QTextEdit()
        self.txt_extract_snippet.setFont(QFont("Consolas", 9))
        self.txt_extract_snippet.setReadOnly(True)
        self.txt_extract_snippet.setFixedHeight(90)
        ec_layout.addWidget(self.txt_extract_snippet)
        self.thought_layout.addWidget(self.extract_card)

        # Card C: Step-by-Step Chain of Thought
        self.chain_card = QFrame()
        self.chain_card.setObjectName("card_options")
        cc_layout = QVBoxLayout(self.chain_card)
        self.lbl_chain_head = QLabel("🧠 " + tr("ai_live.step_reasoning"))
        self.lbl_chain_head.setFont(QFont("Inter", 10, QFont.Weight.Bold))
        cc_layout.addWidget(self.lbl_chain_head)

        self.txt_chain_steps = QTextEdit()
        self.txt_chain_steps.setFont(QFont("Inter", 9))
        self.txt_chain_steps.setReadOnly(True)
        self.txt_chain_steps.setFixedHeight(120)
        cc_layout.addWidget(self.txt_chain_steps)
        self.thought_layout.addWidget(self.chain_card)

        # Card D: Structured JSON Output (GBNF Grammar)
        self.json_card = QFrame()
        self.json_card.setObjectName("card_options")
        jc_layout = QVBoxLayout(self.json_card)
        self.lbl_json_head = QLabel("📊 " + tr("ai_live.step_decision"))
        self.lbl_json_head.setFont(QFont("Inter", 10, QFont.Weight.Bold))
        jc_layout.addWidget(self.lbl_json_head)

        self.txt_json_output = QTextEdit()
        self.txt_json_output.setFont(QFont("Consolas", 9))
        self.txt_json_output.setReadOnly(True)
        self.txt_json_output.setFixedHeight(110)
        jc_layout.addWidget(self.txt_json_output)
        self.thought_layout.addWidget(self.json_card)

        self.thought_layout.addStretch(1)

        right_scroll.setWidget(right_content)
        splitter.addWidget(right_scroll)

        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)

        main_layout.addWidget(splitter, 1)

    def load_items(self, items: List[Dict[str, Any]]):
        """Loads files from the workspace into the live inspector."""
        self.current_items = items
        self.file_list.clear()

        for it in items:
            rel = it.get("rel_path") or Path(it.get("abs_path", "")).name
            cat = it.get("category") or "Pendente"
            conf = it.get("confidence", 0.0)

            item = QListWidgetItem(f"📄 {rel}  [{cat} · {conf * 100:.0f}%]")
            item.setData(Qt.ItemDataRole.UserRole, rel)
            self.file_list.addItem(item)

        if self.file_list.count() > 0:
            self.file_list.setCurrentRow(0)

    def start_live_analysis(self):
        if not self.current_items:
            return

        self.btn_analyze_all.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(len(self.current_items))
        self.progress_bar.setValue(0)

        self.worker = AILiveInspectorWorker(self.current_items, parent=self)
        self.worker.file_analysis_started.connect(self.on_file_started)
        self.worker.file_thought_updated.connect(self.on_thought_received)
        self.worker.analysis_finished.connect(self.on_analysis_finished)
        self.worker.start()

    def stop_live_analysis(self):
        if self.worker:
            self.worker.cancel()
        self.btn_analyze_all.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.progress_bar.setVisible(False)
        self.lbl_subtitle.setText(tr("ai_live.subtitle"))

    def on_file_started(self, filename: str, curr: int, total: int):
        self.progress_bar.setValue(curr)
        self.lbl_subtitle.setText(f"⚡ Analisando IA ({curr}/{total}): {filename}...")

        # Find matching item in list, select it and scroll into view
        for idx in range(self.file_list.count()):
            it = self.file_list.item(idx)
            if it.data(Qt.ItemDataRole.UserRole) == filename:
                self.file_list.setCurrentRow(idx)
                self.file_list.scrollToItem(it)
                it.setText(f"⚡ [Analisando {curr}/{total}] {filename}")
                it.setForeground(QColor("#f59e0b"))
                break

        # Show live loading stream on right panel
        self.lbl_thought_file.setText(f"⚡ Analisando: {filename}...")
        self.lbl_thought_summary.setText(
            f"🧠 <b>Status:</b> <span style='color: #f59e0b;'>Extraindo dados e executando inferência de IA local ({curr}/{total})...</span>"
        )
        self.txt_extract_snippet.setPlainText("⏳ Lendo metadados do arquivo e extraindo conteúdo textual...")
        self.txt_chain_steps.setPlainText(
            f"1. 📥 Abrindo arquivo '{filename}' para leitura de metadados...\n"
            f"2. 🔍 Buscando palavras-chave e similaridade semântica...\n"
            f"3. 🧠 Consultando regras ativas e embeddings vetoriais..."
        )
        self.txt_json_output.setPlainText("{\n  \"status\": \"processando_inferencia_local...\",\n  \"arquivo\": \"" + filename + "\"\n}")

    def on_thought_received(self, thought: Dict[str, Any]):
        rel = thought["rel_path"]
        self.thoughts_cache[rel] = thought

        # Update matching list item with green checkmark
        for idx in range(self.file_list.count()):
            it = self.file_list.item(idx)
            if it.data(Qt.ItemDataRole.UserRole) == rel:
                it.setText(f"✓ {rel}  [{thought['categoria']} · {thought['confianca'] * 100:.0f}% · {thought['elapsed_ms']:.1f}ms]")
                it.setForeground(QColor("#22c55e"))
                break

        # Render active thought immediately
        self.render_thought(thought)

    def on_analysis_finished(self, total: int):
        self.btn_analyze_all.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.progress_bar.setVisible(False)
        self.lbl_subtitle.setText(f"✓ Análise de pensamento da IA concluída para todos os {total} arquivos!")

    def on_file_selected(self, current: Optional[QListWidgetItem], previous: Optional[QListWidgetItem]):
        if not current:
            return

        rel = current.data(Qt.ItemDataRole.UserRole)
        if rel in self.thoughts_cache:
            self.render_thought(self.thoughts_cache[rel])
        else:
            # Fallback: run on-demand inspection for this single file
            matching_item = next((it for it in self.current_items if (it.get("rel_path") or Path(it.get("abs_path", "")).name) == rel), None)
            if matching_item:
                tester = AITester()
                start_t = time.perf_counter()
                diag = tester.diagnose_query(f"{rel} {matching_item.get('extracted_text', '')[:300]}")
                elapsed_ms = (time.perf_counter() - start_t) * 1000.0
                ext = matching_item.get("extension") or Path(rel).suffix
                extracted = matching_item.get("extracted_text") or "(Sem texto extraído ou binário)"

                thought = {
                    "rel_path": rel,
                    "abs_path": matching_item.get("abs_path", ""),
                    "size": matching_item.get("size", 0),
                    "ext": ext,
                    "categoria": diag.categoria,
                    "subcategoria": diag.subcategoria,
                    "tags": diag.tags,
                    "confianca": diag.confianca,
                    "engine_label": diag.engine_label,
                    "elapsed_ms": elapsed_ms,
                    "resumo": diag.reasoning,
                    "extracted_snippet": extracted[:400],
                    "proposed_name": matching_item.get("suggested_filename") or rel,
                    "steps": [
                        f"1. 📥 Metadados lidos: Extensão {ext}, Tamanho {matching_item.get('size', 0) / 1024:.1f} KB.",
                        f"2. 🔍 Extração de Texto: {len(extracted)} caracteres analisados.",
                        f"3. 🧠 Motor de Inferência: {diag.engine_label} acionado.",
                        f"4. 🎯 Similaridade / Regra: Categoria '{diag.categoria}' com {diag.confianca * 100:.1f}% de certeza.",
                        f"5. 📐 Padronização: Destino sugerido em '{diag.categoria}/{diag.subcategoria or 'Geral'}'.",
                    ],
                    "raw_decision": {
                        "categoria": diag.categoria,
                        "subcategoria": diag.subcategoria,
                        "tags": diag.tags,
                        "confianca": round(diag.confianca, 3),
                        "motor": diag.engine_label,
                        "tempo_ms": round(elapsed_ms, 2),
                        "resumo": diag.reasoning,
                    }
                }
                self.thoughts_cache[rel] = thought
                self.render_thought(thought)

    def render_thought(self, thought: Dict[str, Any]):
        rel = thought["rel_path"]
        cat = thought["categoria"]
        sub = thought.get("subcategoria", "")
        conf = thought["confianca"]
        elapsed = thought["elapsed_ms"]
        engine = thought["engine_label"]

        # Update engine badge styling based on tier
        if "Tier 3" in engine or "SLM" in engine:
            self.lbl_engine_badge.setText(f"🦙 {engine}")
            self.lbl_engine_badge.setStyleSheet("background: #9333ea22; color: #a855f7; border: 1px solid #a855f7; border-radius: 12px; padding: 3px 10px; font-weight: bold;")
        elif "Tier 2" in engine or "Busca" in engine or "ONNX" in engine:
            self.lbl_engine_badge.setText(f"🌐 {engine}")
            self.lbl_engine_badge.setStyleSheet("background: #2563eb22; color: #3b82f6; border: 1px solid #3b82f6; border-radius: 12px; padding: 3px 10px; font-weight: bold;")
        else:
            self.lbl_engine_badge.setText(f"⚡ {engine}")
            self.lbl_engine_badge.setStyleSheet("background: #05966922; color: #10b981; border: 1px solid #10b981; border-radius: 12px; padding: 3px 10px; font-weight: bold;")

        self.lbl_thought_file.setText(f"📄 {rel}")
        self.lbl_thought_summary.setText(
            f"🎯 <b>Categoria:</b> <span style='color: #2563eb; font-weight: bold;'>{cat} / {sub or 'Geral'}</span> &nbsp;|&nbsp; "
            f"⚡ <b>Confiança:</b> <span style='color: #22c55e; font-weight: bold;'>{conf * 100:.1f}%</span> &nbsp;|&nbsp; "
            f"⏱️ <b>Latência:</b> {elapsed:.2f}ms &nbsp;|&nbsp; "
            f"🧠 <b>Motor:</b> {engine}\n<br>"
            f"💡 <i>{thought.get('resumo', '')}</i>"
        )

        self.txt_extract_snippet.setPlainText(thought.get("extracted_snippet", ""))
        self.txt_chain_steps.setPlainText("\n".join(thought.get("steps", [])))
        self.txt_json_output.setPlainText(json.dumps(thought.get("raw_decision", {}), indent=2, ensure_ascii=False))

    def filter_file_list(self, text: str):
        query = text.strip().lower()
        for idx in range(self.file_list.count()):
            it = self.file_list.item(idx)
            it.setHidden(query not in it.text().lower())

    def retranslate_ui(self):
        self.lbl_title.setText(f"🧠 {tr('ai_live.title')}")
        self.lbl_subtitle.setText(tr("ai_live.subtitle"))
        self.btn_analyze_all.setText(tr("ai_live.btn_analyze_all"))
        self.btn_stop.setText(tr("ai_live.btn_stop"))
        self.lbl_ext_head.setText("🔍 " + tr("ai_live.step_extract"))
        self.lbl_chain_head.setText("🧠 " + tr("ai_live.step_reasoning"))
        self.lbl_json_head.setText("📊 " + tr("ai_live.step_decision"))
