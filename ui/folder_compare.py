import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem,
    QPushButton, QToolBar, QFileDialog, QLabel, QCheckBox,
    QLineEdit, QAbstractItemView, QHeaderView, QFrame
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QColor, QBrush

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
    open_text_compare = pyqtSignal(str, str)  # (left_path, right_path)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._left_root  = ""
        self._right_root = ""
        self._setup_ui()
        self.setAcceptDrops(True)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._build_toolbar())
        layout.addWidget(self._build_header())
        layout.addWidget(self._build_filter_bar())

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

        layout.addWidget(self._build_legend())
        self._apply_stylesheet()

    def _build_toolbar(self) -> QToolBar:
        tb = QToolBar(); tb.setMovable(False)
        for label, slot in [
            ("왼쪽 폴더 열기",  self._open_left),
            ("오른쪽 폴더 열기", self._open_right),
            ("새로고침",         self._refresh),
        ]:
            b = QPushButton(label)
            b.clicked.connect(slot)
            tb.addWidget(b)
        return tb

    def _build_header(self) -> QWidget:
        w = QWidget(); w.setFixedHeight(28)
        lay = QHBoxLayout(w); lay.setContentsMargins(4, 2, 4, 2)
        self._lbl_left  = QLabel("(폴더 없음)")
        self._lbl_right = QLabel("(폴더 없음)")
        for lbl in (self._lbl_left, self._lbl_right):
            lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        lay.addWidget(self._lbl_left)
        lay.addWidget(QLabel("↔"))
        lay.addWidget(self._lbl_right)
        return w

    def _build_filter_bar(self) -> QWidget:
        w = QWidget(); w.setFixedHeight(32)
        lay = QHBoxLayout(w); lay.setContentsMargins(6, 2, 6, 2); lay.setSpacing(8)

        lay.addWidget(QLabel("패턴 무시:"))
        self._inp_ignore = QLineEdit()
        self._inp_ignore.setPlaceholderText("*.log *.tmp (공백으로 구분)")
        self._inp_ignore.setFixedWidth(200)
        self._inp_ignore.returnPressed.connect(self._refresh)
        lay.addWidget(self._inp_ignore)

        self._chk_hide_same = QCheckBox("동일 파일 숨기기")
        self._chk_hide_same.stateChanged.connect(self._refresh)
        lay.addWidget(self._chk_hide_same)

        lay.addStretch()
        return w

    def _build_legend(self) -> QWidget:
        w = QWidget(); w.setFixedHeight(28)
        lay = QHBoxLayout(w); lay.setContentsMargins(8, 0, 8, 0); lay.setSpacing(16)
        for status, label in STATUS_LABELS.items():
            lbl = QLabel(f"{STATUS_SYMBOLS[status]}  {label}")
            lbl.setStyleSheet(f"color:{STATUS_COLORS[status].name()}; font-size:11px;")
            lay.addWidget(lbl)
        lay.addStretch()
        return w

    def _apply_stylesheet(self):
        self.setStyleSheet("""
            QWidget { background:#1e1e1e; color:#d4d4d4; }
            QPushButton { background:#2d2d2d; color:#d4d4d4; border:1px solid #3c3c3c; padding:3px 8px; border-radius:3px; }
            QPushButton:hover { background:#3a3a3a; }
            QToolBar { background:#252526; border-bottom:1px solid #3c3c3c; spacing:4px; padding:2px; }
            QLabel { color:#d4d4d4; padding:0 4px; }
            QLineEdit { background:#2d2d2d; color:#d4d4d4; border:1px solid #3c3c3c; padding:2px 4px; border-radius:3px; }
            QCheckBox { color:#d4d4d4; }
            QTreeWidget { background:#1e1e1e; color:#d4d4d4; border:none; outline:none; }
            QTreeWidget::item:selected { background:#094771; }
            QTreeWidget::item:hover { background:#2a2d2e; }
            QHeaderView::section { background:#252526; color:#d4d4d4; border:none; border-right:1px solid #3c3c3c; padding:4px; }
        """)

    # ── 폴더 열기 ─────────────────────────────────────────

    def _open_left(self):
        p = QFileDialog.getExistingDirectory(self, "왼쪽 폴더 선택")
        if p:
            self._left_root = p; self._lbl_left.setText(p); self._refresh()

    def _open_right(self):
        p = QFileDialog.getExistingDirectory(self, "오른쪽 폴더 선택")
        if p:
            self._right_root = p; self._lbl_right.setText(p); self._refresh()

    def load_folders(self, left: str, right: str):
        self._left_root = left; self._right_root = right
        self._lbl_left.setText(left); self._lbl_right.setText(right)
        self._refresh()

    # ── 필터 ─────────────────────────────────────────────

    def _get_ignore_patterns(self) -> list[str]:
        raw = self._inp_ignore.text().strip()
        return raw.split() if raw else []

    def _should_show(self, entry: FileEntry) -> bool:
        if self._chk_hide_same.isChecked() and entry.status == FileStatus.IDENTICAL and not entry.is_dir:
            return False
        patterns = self._get_ignore_patterns()
        import fnmatch
        for pat in patterns:
            if fnmatch.fnmatch(entry.name, pat):
                return False
        return True

    # ── 트리 구성 ─────────────────────────────────────────

    def _refresh(self):
        self._tree.clear()
        if not self._left_root or not self._right_root:
            return
        entries = scan_folders(self._left_root, self._right_root)
        for entry in entries:
            self._add_item(self._tree.invisibleRootItem(), entry)
        self._tree.expandAll()

    def _add_item(self, parent: QTreeWidgetItem, entry: FileEntry):
        if not self._should_show(entry):
            return
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

    # ── 더블클릭 ──────────────────────────────────────────

    def _on_double_click(self, item: QTreeWidgetItem, _col: int):
        entry: FileEntry = item.data(0, Qt.ItemDataRole.UserRole)
        if entry is None or entry.is_dir:
            return
        if entry.status in (FileStatus.IDENTICAL, FileStatus.DIFFERENT):
            self.open_text_compare.emit(
                os.path.join(self._left_root, entry.rel_path),
                os.path.join(self._right_root, entry.rel_path),
            )

    # ── 드래그 앤 드롭 ────────────────────────────────────

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        paths = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
        dirs  = [p for p in paths if os.path.isdir(p)]
        if len(dirs) >= 2:
            self.load_folders(dirs[0], dirs[1])
        elif len(dirs) == 1:
            self._left_root = dirs[0]; self._lbl_left.setText(dirs[0]); self._refresh()

    def get_session_info(self) -> dict:
        return {"left": self._left_root, "right": self._right_root}
