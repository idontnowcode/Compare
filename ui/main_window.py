from PyQt6.QtWidgets import (
    QMainWindow, QTabWidget, QWidget, QMenuBar, QMenu, QStatusBar
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction

from ui.text_compare import TextCompareWidget
from ui.folder_compare import FolderCompareWidget


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Compare")
        self.resize(1200, 750)
        self._setup_ui()
        self._setup_menu()
        self._apply_stylesheet()

    def _setup_ui(self):
        self._tabs = QTabWidget()
        self._tabs.setTabsClosable(True)
        self._tabs.tabCloseRequested.connect(self._close_tab)
        self.setCentralWidget(self._tabs)

        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._status.showMessage("준비")

        # 기본 텍스트 비교 탭
        self._add_text_tab()

    def _setup_menu(self):
        menu_bar = self.menuBar()

        # 파일 메뉴
        file_menu = menu_bar.addMenu("파일(&F)")

        act_new_text = QAction("새 텍스트 비교(&T)", self)
        act_new_text.setShortcut("Ctrl+T")
        act_new_text.triggered.connect(self._add_text_tab)
        file_menu.addAction(act_new_text)

        act_new_folder = QAction("새 폴더 비교(&D)", self)
        act_new_folder.setShortcut("Ctrl+D")
        act_new_folder.triggered.connect(self._add_folder_tab)
        file_menu.addAction(act_new_folder)

        file_menu.addSeparator()

        act_quit = QAction("종료(&Q)", self)
        act_quit.setShortcut("Ctrl+Q")
        act_quit.triggered.connect(self.close)
        file_menu.addAction(act_quit)

        # 보기 메뉴
        view_menu = menu_bar.addMenu("보기(&V)")

        act_next_diff = QAction("다음 변경사항", self)
        act_next_diff.setShortcut("F7")
        act_next_diff.triggered.connect(self._next_diff)
        view_menu.addAction(act_next_diff)

        act_prev_diff = QAction("이전 변경사항", self)
        act_prev_diff.setShortcut("Shift+F7")
        act_prev_diff.triggered.connect(self._prev_diff)
        view_menu.addAction(act_prev_diff)

    # ── 탭 관리 ────────────────────────────────────────────

    def _add_text_tab(self):
        widget = TextCompareWidget()
        idx = self._tabs.addTab(widget, "텍스트 비교")
        self._tabs.setCurrentIndex(idx)

    def _add_folder_tab(self):
        widget = FolderCompareWidget()
        widget.open_text_compare.connect(self._open_text_compare_from_folder)
        idx = self._tabs.addTab(widget, "폴더 비교")
        self._tabs.setCurrentIndex(idx)

    def _close_tab(self, index: int):
        if self._tabs.count() > 1:
            self._tabs.removeTab(index)

    def _open_text_compare_from_folder(self, left_path: str, right_path: str):
        import os
        widget = TextCompareWidget()
        widget.load_files(left_path, right_path)
        label = f"{os.path.basename(left_path)} ↔ {os.path.basename(right_path)}"
        idx = self._tabs.addTab(widget, label)
        self._tabs.setCurrentIndex(idx)
        self._status.showMessage(f"비교 중: {left_path}")

    # ── 단축키 액션 ────────────────────────────────────────

    def _current_text_widget(self):
        w = self._tabs.currentWidget()
        return w if isinstance(w, TextCompareWidget) else None

    def _next_diff(self):
        w = self._current_text_widget()
        if w:
            w._next_diff()

    def _prev_diff(self):
        w = self._current_text_widget()
        if w:
            w._prev_diff()

    def _apply_stylesheet(self):
        self.setStyleSheet("""
            QMainWindow { background: #1e1e1e; }
            QMenuBar { background: #252526; color: #d4d4d4; }
            QMenuBar::item:selected { background: #094771; }
            QMenu { background: #252526; color: #d4d4d4; border: 1px solid #3c3c3c; }
            QMenu::item:selected { background: #094771; }
            QTabWidget::pane { border: none; background: #1e1e1e; }
            QTabBar::tab {
                background: #2d2d2d; color: #d4d4d4;
                padding: 6px 16px; border: 1px solid #3c3c3c;
                border-bottom: none; border-radius: 3px 3px 0 0;
            }
            QTabBar::tab:selected { background: #1e1e1e; color: #ffffff; }
            QTabBar::tab:hover { background: #3a3a3a; }
            QStatusBar { background: #007acc; color: #ffffff; font-size: 11px; }
        """)
