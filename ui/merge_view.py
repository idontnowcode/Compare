"""3-way merge 뷰."""
import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QLabel,
    QPushButton, QToolBar, QFileDialog, QMessageBox, QFrame,
    QTextEdit, QListWidget, QListWidgetItem
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QColor, QTextCharFormat, QFont, QTextCursor

from core.merge_engine import three_way_merge, chunks_to_text, ChunkType, MergeChunk
from ui.text_compare import DiffEditor, DiffHighlighter, _THEME
from core.diff_engine import LineType, DiffLine


CHUNK_COLORS = {
    ChunkType.UNCHANGED:  QColor("#1e1e1e"),
    ChunkType.LEFT_ONLY:  QColor("#1a3d1a"),
    ChunkType.RIGHT_ONLY: QColor("#1a2d3d"),
    ChunkType.BOTH_SAME:  QColor("#3d3010"),
    ChunkType.CONFLICT:   QColor("#5a1a1a"),
}


class MergeView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._base_path  = ""
        self._left_path  = ""
        self._right_path = ""
        self._chunks: list[MergeChunk] = []
        self._setup_ui()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_toolbar())
        root.addWidget(self._build_path_header())

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self._left_ed   = DiffEditor()
        self._base_ed   = DiffEditor()
        self._right_ed  = DiffEditor()
        self._result_ed = DiffEditor()
        self._result_ed.set_editable(True)

        for ed, title in [
            (self._left_ed, "My (좌측)"),
            (self._base_ed, "Base (기준)"),
            (self._right_ed, "Their (우측)"),
            (self._result_ed, "결과 (편집 가능)"),
        ]:
            container = QWidget()
            vl = QVBoxLayout(container)
            vl.setContentsMargins(0, 0, 0, 0)
            vl.setSpacing(0)
            lbl = QLabel(title)
            lbl.setFixedHeight(22)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("background:#252526; color:#d4d4d4; font-weight:bold;")
            vl.addWidget(lbl)
            vl.addWidget(ed)
            splitter.addWidget(container)

        root.addWidget(splitter)

        # 충돌 목록 + 해결 버튼
        root.addWidget(self._build_conflict_bar())
        self._apply_stylesheet()

    def _build_toolbar(self) -> QToolBar:
        tb = QToolBar(); tb.setMovable(False)
        for label, slot in [
            ("Base 열기",  self._open_base),
            ("My 열기",    self._open_left),
            ("Their 열기", self._open_right),
            ("병합 실행",   self._run_merge),
            ("결과 저장",   self._save_result),
        ]:
            b = QPushButton(label)
            b.clicked.connect(slot)
            tb.addWidget(b)
        return tb

    def _build_path_header(self) -> QWidget:
        w = QWidget(); w.setFixedHeight(24)
        lay = QHBoxLayout(w); lay.setContentsMargins(4, 0, 4, 0)
        self._lbl_paths = QLabel("Base ↔ My ↔ Their")
        lay.addWidget(self._lbl_paths)
        return w

    def _build_conflict_bar(self) -> QWidget:
        w = QWidget(); w.setFixedHeight(36)
        lay = QHBoxLayout(w); lay.setContentsMargins(6, 2, 6, 2)
        self._lbl_conflict = QLabel("충돌: 0개")
        self._btn_take_left  = QPushButton("← My 채택")
        self._btn_take_right = QPushButton("Their 채택 →")
        self._btn_take_left.clicked.connect(self._take_left)
        self._btn_take_right.clicked.connect(self._take_right)
        for w2 in [self._lbl_conflict, self._btn_take_left, self._btn_take_right]:
            lay.addWidget(w2)
        lay.addStretch()
        return w

    def _apply_stylesheet(self):
        self.setStyleSheet("""
            QWidget { background:#1e1e1e; color:#d4d4d4; }
            QPushButton { background:#2d2d2d; color:#d4d4d4; border:1px solid #3c3c3c; padding:3px 8px; border-radius:3px; }
            QPushButton:hover { background:#3a3a3a; }
            QToolBar { background:#252526; border-bottom:1px solid #3c3c3c; spacing:4px; padding:2px; }
            QLabel { color:#d4d4d4; padding:0 4px; }
        """)

    def _open_base(self):
        p, _ = QFileDialog.getOpenFileName(self, "Base 파일 선택")
        if p: self._base_path = p

    def _open_left(self):
        p, _ = QFileDialog.getOpenFileName(self, "My 파일 선택")
        if p: self._left_path = p

    def _open_right(self):
        p, _ = QFileDialog.getOpenFileName(self, "Their 파일 선택")
        if p: self._right_path = p

    def load_files(self, base: str, left: str, right: str):
        self._base_path = base
        self._left_path = left
        self._right_path = right
        self._run_merge()

    def _read(self, p: str) -> str:
        try:
            with open(p, encoding="utf-8", errors="replace") as f:
                return f.read()
        except OSError:
            return ""

    def _run_merge(self):
        base  = self._read(self._base_path)
        left  = self._read(self._left_path)
        right = self._read(self._right_path)

        self._base_ed.setPlainText(base)
        self._left_ed.setPlainText(left)
        self._right_ed.setPlainText(right)

        self._chunks, has_conflict = three_way_merge(base, left, right)
        conflict_count = sum(1 for c in self._chunks if c.chunk_type == ChunkType.CONFLICT)
        self._lbl_conflict.setText(f"충돌: {conflict_count}개")

        result = chunks_to_text([c for c in self._chunks])
        self._result_ed.setPlainText(result)
        self._highlight_result()

    def _highlight_result(self):
        """결과 패널에서 충돌 라인 강조."""
        extra = []
        block = self._result_ed.document().begin()
        for chunk in self._chunks:
            if chunk.chunk_type == ChunkType.CONFLICT:
                for _ in chunk.result_lines:
                    if block.isValid():
                        sel = QTextEdit.ExtraSelection()
                        sel.format.setBackground(CHUNK_COLORS[ChunkType.CONFLICT])
                        sel.format.setProperty(
                            QTextCharFormat.Property.FullWidthSelection, True
                        )
                        sel.cursor = QTextCursor(block)
                        extra.append(sel)
                        block = block.next()
            else:
                for _ in chunk.result_lines:
                    if block.isValid():
                        block = block.next()
        self._result_ed.setExtraSelections(extra)

    def _take_left(self):
        for chunk in self._chunks:
            if chunk.chunk_type == ChunkType.CONFLICT:
                chunk.resolved = True
                chunk.resolved_lines = chunk.left_lines
        self._result_ed.setPlainText(chunks_to_text(self._chunks))

    def _take_right(self):
        for chunk in self._chunks:
            if chunk.chunk_type == ChunkType.CONFLICT:
                chunk.resolved = True
                chunk.resolved_lines = chunk.right_lines
        self._result_ed.setPlainText(chunks_to_text(self._chunks))

    def _save_result(self):
        p, _ = QFileDialog.getSaveFileName(self, "결과 저장")
        if not p: return
        try:
            with open(p, "w", encoding="utf-8") as f:
                f.write(self._result_ed.toPlainText())
        except OSError as e:
            QMessageBox.critical(self, "저장 실패", str(e))
