import os
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QScrollBar,
    QAbstractScrollArea, QSizePolicy, QPushButton, QToolBar,
    QFileDialog, QSplitter, QFrame
)
from PyQt6.QtCore import Qt, QRect, pyqtSignal, QSize
from PyQt6.QtGui import (
    QPainter, QColor, QFont, QFontMetrics, QPen, QTextOption
)

from core.diff_engine import compute_diff, LineType, DiffLine

COLORS = {
    LineType.EQUAL:   QColor("#1e1e1e"),
    LineType.INSERT:  QColor("#1a3d1a"),
    LineType.DELETE:  QColor("#3d1a1a"),
    LineType.REPLACE: QColor("#3d3010"),
    LineType.EMPTY:   QColor("#2a2a2a"),
}
LINE_NO_BG = QColor("#252526")
LINE_NO_FG = QColor("#858585")
TEXT_FG    = QColor("#d4d4d4")
CURRENT_DIFF_HIGHLIGHT = QColor(255, 255, 255, 25)


class DiffPanel(QAbstractScrollArea):
    """단일 패널 (왼쪽 또는 오른쪽) - diff 라인을 렌더링."""

    scrolled = pyqtSignal(int)  # 스크롤 동기화용

    def __init__(self, parent=None):
        super().__init__(parent)
        self.lines: list[DiffLine] = []
        self._font = QFont("Consolas", 10)
        if not QFontMetrics(self._font).horizontalAdvance("A"):
            self._font = QFont("Monospace", 10)
        self._fm = QFontMetrics(self._font)
        self._line_height = self._fm.height() + 2
        self._line_no_width = 50
        self._current_diff_idx: int = -1  # 강조할 diff 블록 인덱스
        self._diff_block_starts: list[int] = []

        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.verticalScrollBar().valueChanged.connect(self.scrolled.emit)
        self.setFrameShape(QFrame.Shape.NoFrame)

    def set_lines(self, lines: list[DiffLine]):
        self.lines = lines
        self._compute_diff_blocks()
        self._update_scrollbars()
        self.viewport().update()

    def _compute_diff_blocks(self):
        self._diff_block_starts = []
        prev_equal = True
        for i, line in enumerate(self.lines):
            is_diff = line.line_type != LineType.EQUAL
            if is_diff and prev_equal:
                self._diff_block_starts.append(i)
            prev_equal = not is_diff

    def set_current_diff(self, idx: int):
        self._current_diff_idx = idx
        if 0 <= idx < len(self._diff_block_starts):
            row = self._diff_block_starts[idx]
            self._scroll_to_row(row)
        self.viewport().update()

    def _scroll_to_row(self, row: int):
        vb = self.verticalScrollBar()
        target = row * self._line_height - self.viewport().height() // 3
        vb.setValue(max(0, target))

    def diff_block_count(self) -> int:
        return len(self._diff_block_starts)

    def sync_scroll(self, value: int):
        self.verticalScrollBar().setValue(value)

    def _update_scrollbars(self):
        total_height = len(self.lines) * self._line_height
        max_width = max((self._fm.horizontalAdvance(l.text) for l in self.lines), default=0)
        total_width = max_width + self._line_no_width + 20

        self.verticalScrollBar().setRange(0, max(0, total_height - self.viewport().height()))
        self.verticalScrollBar().setPageStep(self.viewport().height())
        self.horizontalScrollBar().setRange(0, max(0, total_width - self.viewport().width()))
        self.horizontalScrollBar().setPageStep(self.viewport().width())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_scrollbars()

    def paintEvent(self, event):
        painter = QPainter(self.viewport())
        painter.setFont(self._font)

        v_offset = self.verticalScrollBar().value()
        h_offset = self.horizontalScrollBar().value()
        vp_height = self.viewport().height()
        vp_width = self.viewport().width()

        first_line = v_offset // self._line_height
        last_line = min(len(self.lines), first_line + vp_height // self._line_height + 2)

        # 현재 diff 블록 행 범위 계산
        current_block_rows: set[int] = set()
        if 0 <= self._current_diff_idx < len(self._diff_block_starts):
            start = self._diff_block_starts[self._current_diff_idx]
            i = start
            while i < len(self.lines) and self.lines[i].line_type != LineType.EQUAL:
                current_block_rows.add(i)
                i += 1

        for row in range(first_line, last_line):
            line = self.lines[row]
            y = row * self._line_height - v_offset
            rect = QRect(0, y, vp_width, self._line_height)

            # 배경
            bg = COLORS.get(line.line_type, COLORS[LineType.EQUAL])
            painter.fillRect(rect, bg)

            # 현재 diff 블록 강조
            if row in current_block_rows:
                painter.fillRect(rect, CURRENT_DIFF_HIGHLIGHT)

            # 라인 번호 배경
            ln_rect = QRect(0, y, self._line_no_width, self._line_height)
            painter.fillRect(ln_rect, LINE_NO_BG)

            # 라인 번호 텍스트
            if line.line_no is not None:
                painter.setPen(LINE_NO_FG)
                painter.drawText(
                    QRect(0, y, self._line_no_width - 6, self._line_height),
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                    str(line.line_no)
                )

            # 구분선
            painter.setPen(QPen(QColor("#3c3c3c")))
            painter.drawLine(self._line_no_width, y, self._line_no_width, y + self._line_height)

            # 텍스트
            if line.text:
                painter.setPen(TEXT_FG)
                text_x = self._line_no_width + 6 - h_offset
                painter.drawText(
                    QRect(text_x, y, vp_width - self._line_no_width - 6, self._line_height),
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                    line.text
                )

        painter.end()


class TextCompareWidget(QWidget):
    """텍스트 비교 뷰 (좌/우 패널 + 툴바)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._left_path: str = ""
        self._right_path: str = ""
        self._current_diff = 0
        self._diff_count = 0
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 툴바
        toolbar = self._build_toolbar()
        layout.addWidget(toolbar)

        # 파일 경로 헤더
        self._header = self._build_header()
        layout.addWidget(self._header)

        # 패널
        splitter = QSplitter(Qt.Orientation.Horizontal)
        self._left_panel = DiffPanel()
        self._right_panel = DiffPanel()
        splitter.addWidget(self._left_panel)
        splitter.addWidget(self._right_panel)
        splitter.setSizes([1, 1])
        layout.addWidget(splitter)

        # 스크롤 동기화
        self._left_panel.scrolled.connect(self._right_panel.sync_scroll)
        self._right_panel.scrolled.connect(self._left_panel.sync_scroll)

        self._apply_stylesheet()

    def _build_toolbar(self) -> QToolBar:
        toolbar = QToolBar()
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(16, 16))

        self._btn_open_left = QPushButton("왼쪽 파일 열기")
        self._btn_open_right = QPushButton("오른쪽 파일 열기")
        self._btn_prev = QPushButton("◀ 이전")
        self._btn_next = QPushButton("다음 ▶")
        self._lbl_diff_pos = QLabel("변경사항: 0 / 0")

        self._btn_open_left.clicked.connect(self._open_left)
        self._btn_open_right.clicked.connect(self._open_right)
        self._btn_prev.clicked.connect(self._prev_diff)
        self._btn_next.clicked.connect(self._next_diff)

        for w in [self._btn_open_left, self._btn_open_right,
                  self._btn_prev, self._btn_next, self._lbl_diff_pos]:
            toolbar.addWidget(w)

        return toolbar

    def _build_header(self) -> QWidget:
        w = QWidget()
        w.setFixedHeight(28)
        lay = QHBoxLayout(w)
        lay.setContentsMargins(4, 2, 4, 2)
        self._lbl_left_path = QLabel("(파일 없음)")
        self._lbl_right_path = QLabel("(파일 없음)")
        self._lbl_left_path.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._lbl_right_path.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        lay.addWidget(self._lbl_left_path)
        lay.addWidget(QLabel("|"))
        lay.addWidget(self._lbl_right_path)
        return w

    def _apply_stylesheet(self):
        self.setStyleSheet("""
            QWidget { background: #1e1e1e; color: #d4d4d4; }
            QPushButton {
                background: #2d2d2d; color: #d4d4d4;
                border: 1px solid #3c3c3c; padding: 3px 8px; border-radius: 3px;
            }
            QPushButton:hover { background: #3a3a3a; }
            QToolBar { background: #252526; border-bottom: 1px solid #3c3c3c; spacing: 4px; padding: 2px; }
            QLabel { color: #d4d4d4; padding: 0 4px; }
            QSplitter::handle { background: #3c3c3c; width: 2px; }
        """)

    # ── 파일 열기 ──────────────────────────────────────────

    def _open_left(self):
        path, _ = QFileDialog.getOpenFileName(self, "왼쪽 파일 선택")
        if path:
            self._left_path = path
            self._lbl_left_path.setText(path)
            self._refresh()

    def _open_right(self):
        path, _ = QFileDialog.getOpenFileName(self, "오른쪽 파일 선택")
        if path:
            self._right_path = path
            self._lbl_right_path.setText(path)
            self._refresh()

    def load_files(self, left_path: str, right_path: str):
        self._left_path = left_path
        self._right_path = right_path
        self._lbl_left_path.setText(left_path)
        self._lbl_right_path.setText(right_path)
        self._refresh()

    def _read(self, path: str) -> str:
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                return f.read()
        except OSError:
            return ""

    def _refresh(self):
        if not self._left_path or not self._right_path:
            return
        left_text = self._read(self._left_path)
        right_text = self._read(self._right_path)
        left_lines, right_lines = compute_diff(left_text, right_text)
        self._left_panel.set_lines(left_lines)
        self._right_panel.set_lines(right_lines)
        self._diff_count = self._left_panel.diff_block_count()
        self._current_diff = 0
        self._update_diff_label()
        if self._diff_count:
            self._left_panel.set_current_diff(0)
            self._right_panel.set_current_diff(0)

    # ── diff 탐색 ──────────────────────────────────────────

    def _prev_diff(self):
        if self._diff_count == 0:
            return
        self._current_diff = (self._current_diff - 1) % self._diff_count
        self._go_to_current_diff()

    def _next_diff(self):
        if self._diff_count == 0:
            return
        self._current_diff = (self._current_diff + 1) % self._diff_count
        self._go_to_current_diff()

    def _go_to_current_diff(self):
        self._left_panel.set_current_diff(self._current_diff)
        self._right_panel.set_current_diff(self._current_diff)
        self._update_diff_label()

    def _update_diff_label(self):
        if self._diff_count:
            self._lbl_diff_pos.setText(f"변경사항: {self._current_diff + 1} / {self._diff_count}")
        else:
            self._lbl_diff_pos.setText("변경사항: 없음")
