import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem,
    QPushButton, QToolBar, QFileDialog, QLabel, QSplitter, QFrame,
    QAbstractItemView, QHeaderView
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QColor, QBrush, QIcon, QFont

from core.folder_scanner import scan_folders, FileEntry, FileStatus

STATUS_COLORS = {
    FileStatus.IDENTICAL: QColor("#4e9a4e"),
    FileStatus.DIFFERENT: QColor("#e8a000"),
    FileStatus.LEFT_ONLY: QColor("#c75151"),
    FileStatus.RIGHT_ONLY: QColor("#5194c7"),
}

STATUS_LABELS = {
    FileStatus.IDENTICAL: "동일",
    FileStatus.DIFFERENT: "다름",
    FileStatus.LEFT_ONLY: "좌측만",
    FileStatus.RIGHT_ONLY: "우측만",
}

STATUS_SYMBOLS = {
    FileStatus.IDENTICAL: "=",
    FileStatus.DIFFERENT: "≠",
    FileStatus.LEFT_ONLY: "←",
    FileStatus.RIGHT_ONLY: "→",
}


class FolderCompareWidget(QWidget):
    """폴더 비교 뷰."""

    open_text_compare = pyqtSignal(str, str)  # (left_path, right_path)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._left_root: str = ""
        self._right_root: str = ""
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 툴바
        toolbar = self._build_toolbar()
        layout.addWidget(toolbar)

        # 경로 헤더
        header = self._build_header()
        layout.addWidget(header)

        # 트리
        self._tree = QTreeWidget()
        self._tree.setColumnCount(3)
        self._tree.setHeaderLabels(["이름", "상태", "경로"])
        self._tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self._tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._tree.header().resizeSection(1, 80)
        self._tree.setAlternatingRowColors(False)
        self._tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._tree.itemDoubleClicked.connect(self._on_double_click)
        layout.addWidget(self._tree)

        # 범례
        legend = self._build_legend()
        layout.addWidget(legend)

        self._apply_stylesheet()

    def _build_toolbar(self) -> QToolBar:
        toolbar = QToolBar()
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(16, 16))

        self._btn_open_left = QPushButton("왼쪽 폴더 열기")
        self._btn_open_right = QPushButton("오른쪽 폴더 열기")
        self._btn_refresh = QPushButton("새로고침")

        self._btn_open_left.clicked.connect(self._open_left)
        self._btn_open_right.clicked.connect(self._open_right)
        self._btn_refresh.clicked.connect(self._refresh)

        for w in [self._btn_open_left, self._btn_open_right, self._btn_refresh]:
            toolbar.addWidget(w)

        return toolbar

    def _build_header(self) -> QWidget:
        w = QWidget()
        w.setFixedHeight(28)
        lay = QHBoxLayout(w)
        lay.setContentsMargins(4, 2, 4, 2)
        self._lbl_left = QLabel("(폴더 없음)")
        self._lbl_right = QLabel("(폴더 없음)")
        self._lbl_left.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._lbl_right.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        lay.addWidget(self._lbl_left)
        lay.addWidget(QLabel("↔"))
        lay.addWidget(self._lbl_right)
        return w

    def _build_legend(self) -> QWidget:
        w = QWidget()
        w.setFixedHeight(28)
        lay = QHBoxLayout(w)
        lay.setContentsMargins(8, 0, 8, 0)
        lay.setSpacing(16)
        for status, label in STATUS_LABELS.items():
            lbl = QLabel(f"{STATUS_SYMBOLS[status]}  {label}")
            color = STATUS_COLORS[status].name()
            lbl.setStyleSheet(f"color: {color}; font-size: 11px;")
            lay.addWidget(lbl)
        lay.addStretch()
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
            QTreeWidget {
                background: #1e1e1e; color: #d4d4d4;
                border: none; outline: none;
            }
            QTreeWidget::item:selected { background: #094771; }
            QTreeWidget::item:hover { background: #2a2d2e; }
            QHeaderView::section {
                background: #252526; color: #d4d4d4;
                border: none; border-right: 1px solid #3c3c3c;
                padding: 4px;
            }
        """)

    # ── 폴더 열기 ──────────────────────────────────────────

    def _open_left(self):
        path = QFileDialog.getExistingDirectory(self, "왼쪽 폴더 선택")
        if path:
            self._left_root = path
            self._lbl_left.setText(path)
            self._refresh()

    def _open_right(self):
        path = QFileDialog.getExistingDirectory(self, "오른쪽 폴더 선택")
        if path:
            self._right_root = path
            self._lbl_right.setText(path)
            self._refresh()

    def load_folders(self, left_path: str, right_path: str):
        self._left_root = left_path
        self._right_root = right_path
        self._lbl_left.setText(left_path)
        self._lbl_right.setText(right_path)
        self._refresh()

    def _refresh(self):
        self._tree.clear()
        if not self._left_root or not self._right_root:
            return
        entries = scan_folders(self._left_root, self._right_root)
        for entry in entries:
            self._add_item(self._tree.invisibleRootItem(), entry)
        self._tree.expandAll()

    def _add_item(self, parent: QTreeWidgetItem, entry: FileEntry):
        prefix = "📁 " if entry.is_dir else "📄 "
        item = QTreeWidgetItem(parent)
        item.setText(0, prefix + entry.name)
        item.setText(1, STATUS_SYMBOLS[entry.status] + "  " + STATUS_LABELS[entry.status])
        item.setText(2, entry.rel_path)
        item.setData(0, Qt.ItemDataRole.UserRole, entry)

        color = STATUS_COLORS[entry.status]
        for col in range(3):
            item.setForeground(col, QBrush(color))

        for child in entry.children:
            self._add_item(item, child)

    # ── 더블 클릭 → 텍스트 비교 ───────────────────────────

    def _on_double_click(self, item: QTreeWidgetItem, column: int):
        entry: FileEntry = item.data(0, Qt.ItemDataRole.UserRole)
        if entry is None or entry.is_dir:
            return
        if entry.status in (FileStatus.IDENTICAL, FileStatus.DIFFERENT):
            left_path = os.path.join(self._left_root, entry.rel_path)
            right_path = os.path.join(self._right_root, entry.rel_path)
            self.open_text_compare.emit(left_path, right_path)
