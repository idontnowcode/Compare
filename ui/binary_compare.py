"""바이너리 파일 비교 뷰 (Hex dump diff)."""
import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSplitter,
    QPushButton, QToolBar, QFileDialog, QPlainTextEdit, QScrollBar
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import (
    QFont, QFontMetrics, QSyntaxHighlighter, QTextCharFormat, QColor,
    QTextDocument
)

BYTES_PER_ROW = 16


def _hex_dump(data: bytes) -> list[str]:
    """바이트 데이터를 hex dump 라인 리스트로 변환."""
    lines = []
    for i in range(0, len(data), BYTES_PER_ROW):
        chunk = data[i:i + BYTES_PER_ROW]
        offset = f"{i:08X}"
        hex_part = " ".join(f"{b:02X}" for b in chunk)
        hex_part = hex_part.ljust(BYTES_PER_ROW * 3 - 1)
        ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        lines.append(f"{offset}  {hex_part}  {ascii_part}")
    return lines


class HexHighlighter(QSyntaxHighlighter):
    def __init__(self, doc: QTextDocument, diff_rows: set[int]):
        super().__init__(doc)
        self._diff_rows = diff_rows

    def set_diff_rows(self, rows: set[int]):
        self._diff_rows = rows
        self.rehighlight()

    def highlightBlock(self, text: str):
        block_num = self.currentBlock().blockNumber()
        if block_num in self._diff_rows:
            fmt = QTextCharFormat()
            fmt.setBackground(QColor("#3d3010"))
            self.setFormat(0, len(text), fmt)


class HexPanel(QPlainTextEdit):
    scrolled = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        font = QFont("Consolas", 10)
        self.setFont(font)
        self.setReadOnly(True)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self._highlighter = HexHighlighter(self.document(), set())
        self.verticalScrollBar().valueChanged.connect(self.scrolled.emit)

    def set_content(self, lines: list[str], diff_rows: set[int]):
        self.setPlainText("\n".join(lines))
        self._highlighter.set_diff_rows(diff_rows)

    def sync_scroll(self, value: int):
        self.verticalScrollBar().setValue(value)


class BinaryCompareWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._left_path  = ""
        self._right_path = ""
        self._setup_ui()
        self.setAcceptDrops(True)

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_toolbar())
        root.addWidget(self._build_path_header())

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self._left_panel  = HexPanel()
        self._right_panel = HexPanel()
        splitter.addWidget(self._left_panel)
        splitter.addWidget(self._right_panel)
        splitter.setSizes([1, 1])
        root.addWidget(splitter)

        root.addWidget(self._build_status_bar())

        self._left_panel.scrolled.connect(self._right_panel.sync_scroll)
        self._right_panel.scrolled.connect(self._left_panel.sync_scroll)
        self._apply_stylesheet()

    def _build_toolbar(self) -> QToolBar:
        tb = QToolBar(); tb.setMovable(False)
        for label, slot in [
            ("왼쪽 파일 열기",  self._open_left),
            ("오른쪽 파일 열기", self._open_right),
        ]:
            b = QPushButton(label); b.clicked.connect(slot); tb.addWidget(b)
        return tb

    def _build_path_header(self) -> QWidget:
        w = QWidget(); w.setFixedHeight(28)
        lay = QHBoxLayout(w); lay.setContentsMargins(4, 2, 4, 2)
        self._lbl_left  = QLabel("(파일 없음)")
        self._lbl_right = QLabel("(파일 없음)")
        lay.addWidget(self._lbl_left)
        lay.addWidget(QLabel("↔"))
        lay.addWidget(self._lbl_right)
        return w

    def _build_status_bar(self) -> QWidget:
        w = QWidget(); w.setFixedHeight(24)
        lay = QHBoxLayout(w); lay.setContentsMargins(8, 0, 8, 0)
        self._lbl_status = QLabel("")
        lay.addWidget(self._lbl_status)
        lay.addStretch()
        return w

    def _apply_stylesheet(self):
        self.setStyleSheet("""
            QWidget { background:#1e1e1e; color:#d4d4d4; }
            QPushButton { background:#2d2d2d; color:#d4d4d4; border:1px solid #3c3c3c; padding:3px 8px; border-radius:3px; }
            QPushButton:hover { background:#3a3a3a; }
            QToolBar { background:#252526; border-bottom:1px solid #3c3c3c; spacing:4px; padding:2px; }
            QLabel { color:#d4d4d4; padding:0 4px; }
            QPlainTextEdit { background:#1e1e1e; color:#d4d4d4; border:none; }
        """)

    def _open_left(self):
        p, _ = QFileDialog.getOpenFileName(self, "왼쪽 바이너리 파일")
        if p: self._left_path = p; self._lbl_left.setText(p); self._refresh()

    def _open_right(self):
        p, _ = QFileDialog.getOpenFileName(self, "오른쪽 바이너리 파일")
        if p: self._right_path = p; self._lbl_right.setText(p); self._refresh()

    def load_files(self, left: str, right: str):
        self._left_path = left; self._right_path = right
        self._lbl_left.setText(left); self._lbl_right.setText(right)
        self._refresh()

    def _refresh(self):
        def read(p: str) -> bytes:
            try:
                with open(p, "rb") as f:
                    return f.read()
            except OSError:
                return b""

        left_data  = read(self._left_path)  if self._left_path  else b""
        right_data = read(self._right_path) if self._right_path else b""

        left_lines  = _hex_dump(left_data)
        right_lines = _hex_dump(right_data)

        # 다른 행 찾기
        diff_rows: set[int] = set()
        for i in range(max(len(left_lines), len(right_lines))):
            ll = left_lines[i]  if i < len(left_lines)  else ""
            rl = right_lines[i] if i < len(right_lines) else ""
            if ll != rl:
                diff_rows.add(i)

        self._left_panel.set_content(left_lines, diff_rows)
        self._right_panel.set_content(right_lines, diff_rows)

        total = max(len(left_data), len(right_data))
        diff_bytes = len(diff_rows) * BYTES_PER_ROW
        self._lbl_status.setText(
            f"크기: 좌 {len(left_data):,}B / 우 {len(right_data):,}B | "
            f"다른 행: {len(diff_rows)} ({diff_bytes}B 범위)"
        )

    # 드래그 앤 드롭
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls(): event.acceptProposedAction()

    def dropEvent(self, event):
        paths = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
        if len(paths) >= 2:
            self.load_files(paths[0], paths[1])
        elif len(paths) == 1:
            self._left_path = paths[0]; self._lbl_left.setText(paths[0]); self._refresh()

    def get_session_info(self) -> dict:
        return {"left": self._left_path, "right": self._right_path}
