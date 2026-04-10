"""Git 연동 뷰 (브랜치/커밋 diff)."""
import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSplitter,
    QPushButton, QToolBar, QFileDialog, QListWidget,
    QListWidgetItem, QComboBox, QTreeWidget, QTreeWidgetItem,
    QMessageBox, QLineEdit, QHeaderView
)
from PyQt6.QtCore import Qt, pyqtSignal

from core import git_integration as git
from ui.text_compare import TextCompareWidget


class GitView(QWidget):
    open_text_compare = pyqtSignal(str, str, str, str)  # (left_text, right_text, left_label, right_label)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._repo_path = ""
        self._commits: list[git.GitCommit] = []
        self._selected_commit1 = ""
        self._selected_commit2 = ""
        self._setup_ui()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_toolbar())

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 왼쪽: 브랜치 + 커밋 목록
        left_panel = QWidget()
        lv = QVBoxLayout(left_panel)
        lv.setContentsMargins(0, 0, 0, 0)

        lv.addWidget(QLabel("브랜치:"))
        self._cmb_branch = QComboBox()
        self._cmb_branch.currentTextChanged.connect(self._load_commits)
        lv.addWidget(self._cmb_branch)

        lv.addWidget(QLabel("커밋 목록:"))
        self._lst_commits = QListWidget()
        self._lst_commits.itemSelectionChanged.connect(self._on_commit_select)
        lv.addWidget(self._lst_commits)

        # 비교할 두 커밋 선택
        lv.addWidget(QLabel("비교:"))
        row = QHBoxLayout()
        self._lbl_c1 = QLabel("(없음)"); self._lbl_c1.setFixedHeight(20)
        self._lbl_c2 = QLabel("(없음)"); self._lbl_c2.setFixedHeight(20)
        self._btn_set1 = QPushButton("A로 설정"); self._btn_set1.clicked.connect(self._set_commit1)
        self._btn_set2 = QPushButton("B로 설정"); self._btn_set2.clicked.connect(self._set_commit2)
        for w in [self._btn_set1, self._btn_set2]:
            row.addWidget(w)
        lv.addLayout(row)
        lv.addWidget(self._lbl_c1)
        lv.addWidget(self._lbl_c2)

        splitter.addWidget(left_panel)

        # 오른쪽: 변경된 파일 목록
        right_panel = QWidget()
        rv = QVBoxLayout(right_panel)
        rv.setContentsMargins(0, 0, 0, 0)
        rv.addWidget(QLabel("변경된 파일:"))
        self._tree_files = QTreeWidget()
        self._tree_files.setColumnCount(1)
        self._tree_files.setHeaderLabels(["파일"])
        self._tree_files.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._tree_files.itemDoubleClicked.connect(self._open_file_diff)
        rv.addWidget(self._tree_files)

        self._btn_diff_all = QPushButton("선택 파일 비교")
        self._btn_diff_all.clicked.connect(self._open_file_diff_selected)
        rv.addWidget(self._btn_diff_all)

        splitter.addWidget(right_panel)
        splitter.setSizes([300, 500])
        root.addWidget(splitter)

        self._apply_stylesheet()

    def _build_toolbar(self) -> QToolBar:
        tb = QToolBar(); tb.setMovable(False)
        btn = QPushButton("저장소 열기"); btn.clicked.connect(self._open_repo)
        tb.addWidget(btn)
        self._lbl_repo = QLabel("(저장소 없음)"); tb.addWidget(self._lbl_repo)
        return tb

    def _apply_stylesheet(self):
        self.setStyleSheet("""
            QWidget { background:#1e1e1e; color:#d4d4d4; }
            QPushButton { background:#2d2d2d; color:#d4d4d4; border:1px solid #3c3c3c; padding:3px 8px; border-radius:3px; }
            QPushButton:hover { background:#3a3a3a; }
            QToolBar { background:#252526; border-bottom:1px solid #3c3c3c; spacing:4px; padding:2px; }
            QLabel { color:#d4d4d4; padding:0 2px; }
            QListWidget { background:#1e1e1e; color:#d4d4d4; border:1px solid #3c3c3c; }
            QListWidget::item:selected { background:#094771; }
            QComboBox { background:#2d2d2d; color:#d4d4d4; border:1px solid #3c3c3c; }
            QTreeWidget { background:#1e1e1e; color:#d4d4d4; border:1px solid #3c3c3c; }
            QTreeWidget::item:selected { background:#094771; }
            QHeaderView::section { background:#252526; color:#d4d4d4; border:none; }
        """)

    def _open_repo(self):
        path = QFileDialog.getExistingDirectory(self, "Git 저장소 선택")
        if not path: return
        try:
            root = git.get_repo_root(path)
            self._repo_path = root
            self._lbl_repo.setText(root)
            branches = git.list_branches(root)
            self._cmb_branch.clear()
            self._cmb_branch.addItems(branches)
            if "main" in branches:
                self._cmb_branch.setCurrentText("main")
            elif "master" in branches:
                self._cmb_branch.setCurrentText("master")
        except Exception as e:
            QMessageBox.critical(self, "오류", str(e))

    def _load_commits(self, branch: str):
        if not self._repo_path or not branch: return
        try:
            self._commits = git.list_commits(self._repo_path, branch)
            self._lst_commits.clear()
            for c in self._commits:
                item = QListWidgetItem(f"{c.short_sha}  {c.date}  {c.message[:60]}")
                item.setData(Qt.ItemDataRole.UserRole, c)
                self._lst_commits.addItem(item)
        except Exception as e:
            QMessageBox.critical(self, "오류", str(e))

    def _on_commit_select(self):
        pass

    def _set_commit1(self):
        item = self._lst_commits.currentItem()
        if item:
            c: git.GitCommit = item.data(Qt.ItemDataRole.UserRole)
            self._selected_commit1 = c.sha
            self._lbl_c1.setText(f"A: {c.short_sha} {c.message[:40]}")
            self._load_changed_files()

    def _set_commit2(self):
        item = self._lst_commits.currentItem()
        if item:
            c: git.GitCommit = item.data(Qt.ItemDataRole.UserRole)
            self._selected_commit2 = c.sha
            self._lbl_c2.setText(f"B: {c.short_sha} {c.message[:40]}")
            self._load_changed_files()

    def _load_changed_files(self):
        if not self._selected_commit1 or not self._selected_commit2: return
        try:
            files = git.list_changed_files(
                self._repo_path, self._selected_commit1, self._selected_commit2
            )
            self._tree_files.clear()
            for f in files:
                item = QTreeWidgetItem(self._tree_files)
                item.setText(0, f)
                item.setData(0, Qt.ItemDataRole.UserRole, f)
        except Exception as e:
            QMessageBox.critical(self, "오류", str(e))

    def _open_file_diff(self, item: QTreeWidgetItem, _col: int):
        rel = item.data(0, Qt.ItemDataRole.UserRole)
        self._compare_file(rel)

    def _open_file_diff_selected(self):
        item = self._tree_files.currentItem()
        if item:
            self._compare_file(item.data(0, Qt.ItemDataRole.UserRole))

    def _compare_file(self, rel_path: str):
        if not self._selected_commit1 or not self._selected_commit2: return
        try:
            c1 = git.get_file_at_commit(self._repo_path, self._selected_commit1, rel_path)
            c2 = git.get_file_at_commit(self._repo_path, self._selected_commit2, rel_path)
            self.open_text_compare.emit(
                c1, c2,
                f"{self._selected_commit1[:7]}:{rel_path}",
                f"{self._selected_commit2[:7]}:{rel_path}",
            )
        except Exception as e:
            QMessageBox.critical(self, "오류", str(e))

    def get_session_info(self) -> dict:
        return {"repo": self._repo_path}
