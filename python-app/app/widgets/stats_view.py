import os
from pathlib import Path
from typing import Dict, List, Any, Optional
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor, QPainter, QBrush, QPen, QLinearGradient
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QProgressBar, QScrollArea, QTableWidget, QTableWidgetItem,
    QHeaderView, QGridLayout, QAbstractItemView
)
from app.i18n.language_manager import tr, LanguageManager
from app.widgets.smooth_scroll import SmoothScrollArea, SmoothTableWidget

def format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.2f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"

class CategoryBarWidget(QWidget):
    """Custom horizontal bar chart widget showing category/type proportions."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.data: List[tuple[str, int, int, str]] = [] # (label, count, size_bytes, color_hex)
        self.setFixedHeight(34)

    def set_data(self, data: List[tuple[str, int, int, str]]):
        self.data = data
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        rect = self.rect()
        total_size = sum(item[2] for item in self.data)
        if total_size <= 0:
            painter.setBrush(QBrush(QColor("#2A2E39")))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(rect, 6, 6)
            return

        x_cursor = 0.0
        width = float(rect.width())
        height = float(rect.height())

        for idx, (label, count, size_bytes, color_hex) in enumerate(self.data):
            fraction = float(size_bytes) / float(total_size)
            bar_w = fraction * width
            if bar_w < 1.0:
                continue

            color = QColor(color_hex)
            painter.setBrush(QBrush(color))
            painter.setPen(Qt.PenStyle.NoPen)

            # Round edges on first and last
            if idx == 0 and len(self.data) == 1:
                painter.drawRoundedRect(int(x_cursor), 0, int(bar_w), int(height), 6, 6)
            else:
                painter.drawRect(int(x_cursor), 0, int(bar_w) + 1, int(height))

            x_cursor += bar_w


class StatsView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.items: List[Dict[str, Any]] = []
        self.duplicates_count = 0
        self.duplicates_bytes = 0
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(16)

        self.scroll = SmoothScrollArea()

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        is_pt = LanguageManager.get_instance().current_language == "ptBR"
        
        # 1. Title
        title_box = QHBoxLayout()
        self.lbl_title = QLabel(tr("stats.title"))
        self.lbl_title.setFont(QFont("Inter", 14, QFont.Weight.Bold))
        title_box.addWidget(self.lbl_title)
        title_box.addStretch()
        layout.addLayout(title_box)

        # 2. KPI Cards Grid
        self.kpi_grid = QGridLayout()
        self.kpi_grid.setSpacing(12)

        lbl_files_title = "Total de Arquivos" if is_pt else "Total Files"
        lbl_size_title = "Espaço Total em Disco" if is_pt else "Total Disk Space"
        lbl_acc_title = "Precisão Semântica" if is_pt else "Semantic Accuracy"
        lbl_dup_title = "Duplicatas & Desperdício" if is_pt else "Duplicates & Waste"

        self.card_files = self.create_kpi_card(lbl_files_title, "0", "Aguardando escaneamento" if is_pt else "Awaiting scan", "#205EA6")
        self.card_size = self.create_kpi_card(lbl_size_title, "0 MB", "Tamanho combinado" if is_pt else "Combined size", "#2E7D32")
        self.card_accuracy = self.create_kpi_card(lbl_acc_title, "0%", "Classificados com alta confiança" if is_pt else "High confidence classified", "#D97706")
        self.card_duplicates = self.create_kpi_card(lbl_dup_title, "0 (0 MB)", "Economia potencial de espaço" if is_pt else "Potential space savings", "#9333EA")

        self.kpi_grid.addWidget(self.card_files["frame"], 0, 0)
        self.kpi_grid.addWidget(self.card_size["frame"], 0, 1)
        self.kpi_grid.addWidget(self.card_accuracy["frame"], 0, 2)
        self.kpi_grid.addWidget(self.card_duplicates["frame"], 0, 3)
        layout.addLayout(self.kpi_grid)

        # 3. Visual Chart: Storage Distribution by File Type
        type_card = QFrame()
        type_card.setObjectName("card_options")
        type_card_layout = QVBoxLayout(type_card)
        type_card_layout.setContentsMargins(16, 16, 16, 16)
        type_card_layout.setSpacing(12)

        self.lbl_chart_title = QLabel(tr("stats.chart_title"))
        self.lbl_chart_title.setFont(QFont("Inter", 11, QFont.Weight.Bold))
        type_card_layout.addWidget(self.lbl_chart_title)

        self.type_bar_chart = CategoryBarWidget()
        type_card_layout.addWidget(self.type_bar_chart)

        self.type_legend_layout = QHBoxLayout()
        self.type_legend_layout.setSpacing(16)
        type_card_layout.addLayout(self.type_legend_layout)

        layout.addWidget(type_card)

        # 4. Detailed Type and Category Breakdown Table
        table_card = QFrame()
        table_card.setObjectName("card_options")
        table_card_layout = QVBoxLayout(table_card)
        table_card_layout.setContentsMargins(16, 16, 16, 16)
        table_card_layout.setSpacing(12)

        self.lbl_table_title = QLabel(tr("stats.table_title"))
        self.lbl_table_title.setFont(QFont("Inter", 11, QFont.Weight.Bold))
        table_card_layout.addWidget(self.lbl_table_title)

        self.table_stats = SmoothTableWidget(0, 5)
        headers = [
            tr("stats.col_category", default="Categoria / Tipo"),
            tr("stats.col_files", default="Quantidade"),
            tr("stats.col_size", default="Tamanho Total"),
            tr("stats.col_percent", default="% do Disco"),
            tr("stats.col_confidence", default="Confiança Média")
        ]
        self.table_stats.setHorizontalHeaderLabels(headers)
        self.table_stats.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table_stats.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table_stats.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table_stats.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table_stats.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table_stats.verticalHeader().setVisible(False)
        self.table_stats.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table_stats.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.table_stats.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table_stats.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.table_stats.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.table_stats.setMinimumHeight(160)
        table_card_layout.addWidget(self.table_stats)

        layout.addWidget(table_card)

        layout.addStretch()
        self.scroll.setWidget(container)
        main_layout.addWidget(self.scroll)

    def create_kpi_card(self, title: str, val: str, sub: str, border_color: str) -> Dict[str, Any]:
        frame = QFrame()
        frame.setObjectName("settings_panel")
        frame.setStyleSheet(f"""
            QFrame {{
                border-left: 4px solid {border_color};
                border-radius: 8px;
                padding: 12px;
            }}
        """)
        l = QVBoxLayout(frame)
        l.setContentsMargins(8, 6, 8, 6)
        l.setSpacing(4)

        lbl_t = QLabel(title)
        lbl_t.setFont(QFont("Inter", 9, QFont.Weight.Medium))
        lbl_t.setStyleSheet("color: #888;")
        l.addWidget(lbl_t)

        lbl_v = QLabel(val)
        lbl_v.setFont(QFont("Inter", 16, QFont.Weight.Bold))
        l.addWidget(lbl_v)

        lbl_s = QLabel(sub)
        lbl_s.setFont(QFont("Inter", 8))
        lbl_s.setStyleSheet("color: #777;")
        l.addWidget(lbl_s)

        return {"frame": frame, "title": lbl_t, "value": lbl_v, "sub": lbl_s}

    def update_stats(self, items: List[Dict[str, Any]], duplicates_count: int = 0, duplicates_bytes: int = 0):
        self.items = items
        self.duplicates_count = duplicates_count
        self.duplicates_bytes = duplicates_bytes

        total_files = len(items)
        total_bytes = sum(it.get("size", 0) for it in items)
        identified_files = sum(1 for it in items if it.get("status") == "identificado")

        # 1. Update KPI cards
        self.card_files["value"].setText(f"{total_files:,}")
        self.card_files["sub"].setText(tr("stats.kpi_files_sub", id_count=identified_files, pend_count=total_files - identified_files))

        self.card_size["value"].setText(format_size(total_bytes))
        avg_size = total_bytes / total_files if total_files > 0 else 0
        self.card_size["sub"].setText(tr("stats.kpi_size_sub", avg_size=format_size(int(avg_size))))

        acc_pct = (identified_files / total_files * 100) if total_files > 0 else 0
        self.card_accuracy["value"].setText(f"{acc_pct:.1f}%")
        self.card_accuracy["sub"].setText(tr("stats.card_acc_sub"))

        self.card_duplicates["value"].setText(f"{duplicates_count:,} ({format_size(duplicates_bytes)})")
        self.card_duplicates["sub"].setText(tr("stats.card_dup_sub"))

        # 2. Group by Type for Chart
        is_pt = LanguageManager.get_instance().current_language == "ptBR"
        type_palette = {
            "document": ("#205EA6", "Documentos (PDF, DOCX)" if is_pt else "Documents (PDF, DOCX)"),
            "image": ("#2E7D32", "Imagens (PNG, JPG)" if is_pt else "Images (PNG, JPG)"),
            "audio": ("#D97706", "Áudio" if is_pt else "Audio"),
            "video": ("#9333EA", "Vídeos" if is_pt else "Videos"),
            "text": ("#0D9488", "Textos & Código" if is_pt else "Text & Code"),
            "other": ("#6B7280", "Outros" if is_pt else "Others"),
        }

        type_stats: Dict[str, Dict[str, Any]] = {}
        for it in items:
            ft = it.get("file_type", "other")
            if ft not in type_stats:
                type_stats[ft] = {"count": 0, "size": 0}
            type_stats[ft]["count"] += 1
            type_stats[ft]["size"] += it.get("size", 0)

        chart_data = []
        # Clear existing legend
        while self.type_legend_layout.count() > 0:
            w = self.type_legend_layout.takeAt(0).widget()
            if w:
                w.deleteLater()

        for ft, stats in type_stats.items():
            color_hex, label_name = type_palette.get(ft, ("#6B7280", ft.capitalize()))
            chart_data.append((label_name, stats["count"], stats["size"], color_hex))

            # Add to legend
            pct = (stats["size"] / total_bytes * 100) if total_bytes > 0 else 0
            legend_lbl = QLabel(f"<span style='color:{color_hex}; font-size:14px;'>●</span> <b>{label_name}</b>: {stats['count']} ({format_size(stats['size'])}) — {pct:.1f}%")
            legend_lbl.setFont(QFont("Inter", 9))
            self.type_legend_layout.addWidget(legend_lbl)

        self.type_legend_layout.addStretch()
        self.type_bar_chart.set_data(chart_data)

        # 3. Populate Category Breakdown Table
        cat_stats: Dict[str, Dict[str, Any]] = {}
        for it in items:
            cat = it.get("category", "Outros")
            if cat not in cat_stats:
                cat_stats[cat] = {"count": 0, "size": 0, "conf_sum": 0.0}
            cat_stats[cat]["count"] += 1
            cat_stats[cat]["size"] += it.get("size", 0)
            cat_stats[cat]["conf_sum"] += it.get("confidence", 0.0)

        self.table_stats.setRowCount(0)
        sorted_cats = sorted(cat_stats.items(), key=lambda kv: kv[1]["size"], reverse=True)
        for r_idx, (cat_name, st) in enumerate(sorted_cats):
            self.table_stats.insertRow(r_idx)
            pct = (st["size"] / total_bytes * 100) if total_bytes > 0 else 0
            avg_conf = (st["conf_sum"] / st["count"] * 100) if st["count"] > 0 else 0

            self.table_stats.setItem(r_idx, 0, QTableWidgetItem(f"{cat_name}"))
            self.table_stats.setItem(r_idx, 1, QTableWidgetItem(tr("stats.files_count", count=st['count'])))
            self.table_stats.setItem(r_idx, 2, QTableWidgetItem(format_size(st["size"])))
            self.table_stats.setItem(r_idx, 3, QTableWidgetItem(f"{pct:.1f}%"))
            self.table_stats.setItem(r_idx, 4, QTableWidgetItem(f"{avg_conf:.0f}%"))

        header_h = self.table_stats.horizontalHeader().height() or 28
        total_h = header_h + (len(sorted_cats) * 32) + 8
        self.table_stats.setFixedHeight(max(160, total_h))

        self.table_stats.scrollToTop()
        self.table_stats.setCurrentItem(None)
        if hasattr(self, 'scroll') and self.scroll.verticalScrollBar():
            self.scroll.verticalScrollBar().setValue(0)

    def retranslate_ui(self):
        is_pt = LanguageManager.get_instance().current_language == "ptBR"
        self.lbl_title.setText(tr("stats.title"))
        self.lbl_chart_title.setText(tr("stats.chart_title", default="Distribuição por Tipo de Arquivo"))
        self.lbl_table_title.setText(tr("stats.table_title", default="Detalhamento por Categoria Semântica"))
        headers = [
            tr("stats.col_category", default="Categoria / Tipo"),
            tr("stats.col_files", default="Quantidade"),
            tr("stats.col_size", default="Tamanho Total"),
            tr("stats.col_percent", default="% do Disco"),
            tr("stats.col_confidence", default="Confiança Média")
        ]
        self.table_stats.setHorizontalHeaderLabels(headers)
        self.card_files["title"].setText("Total de Arquivos" if is_pt else "Total Files")
        self.card_size["title"].setText("Espaço Total em Disco" if is_pt else "Total Disk Space")
        self.card_accuracy["title"].setText("Precisão Semântica" if is_pt else "Semantic Accuracy")
        self.card_duplicates["title"].setText("Duplicatas & Desperdício" if is_pt else "Duplicates & Waste")
        if self.items:
            self.update_stats(self.items, self.duplicates_count, self.duplicates_bytes)
