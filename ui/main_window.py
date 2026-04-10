import os
import sys
from PyQt6.QtWidgets import (
    QMainWindow, QTabWidget, QWidget, QMenuBar, QStatusBar,
    QInputDialog, QMessageBox, QApplication
)
from PyQt6.QtCore import Qt, QSettings, QByteArray, QSize
from PyQt6.QtGui import QAction, QKeySequence, QDragEnterEvent, QDropEvent

from ui.text_compare import TextCompareWidget, set_theme
from ui.folder_compare import FolderCompareWidget
from ui.merge_view import MergeView
from ui.image_compare import ImageCompareWidget
from ui.binary_compare import BinaryCompareWidget
from ui.git_view import GitView
from ui.ftp_dialog import FTPDialog
from ui.settings_dialog import SettingsDialog, load_settings
from core.session_manager import (
    AppSession, TabSession,
    save_session, load_session, add_recent, load_recent,
)
import core.git_integration as git


SETTINGS_ORG = "CompareApp"
SETTINGS_APP = "MainWindow"


class MainWindow(QMainWindow):
    def __init__(self, cli_files: list[str] | None = None):
        super().__init__()
        self.setWindowTitle("Compare")
        self.resize(1280, 800)
        self.setAcceptDrops(True)

        self._cfg = load_settings()
        set_theme(self._cfg.get("theme", "dark"))

        self._setup_ui()
        self._setup_menu()
        self._apply_stylesheet()
        self._restore_layout()

        # 세션 복원 또는 CLI 인자 처리
        if cli_files and len(cli_files) >= 2:
            self._add_text_tab(cli_files[0], cli_files[1])
        elif self._cfg.get("restore_session"):
            self._restore_session()
        else:
            self._add_text_tab()

    # ── UI 구성 ────────────────────────────────────────────

    def _setup_ui(self):
        self._tabs = QTabWidget()
        self._tabs.setTabsClosable(True)
        self._tabs.tabCloseRequested.connect(self._close_tab)
        self._tabs.tabBarDoubleClicked.connect(self._rename_tab)
        self.setCentralWidget(self._tabs)

        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._status.showMessage("준비")

    def _setup_menu(self):
        mb = self.menuBar()

        # ── 파일 메뉴 ─────────────────────────────────────
        file_menu = mb.addMenu("파일(&F)")
        self._add_action(file_menu, "새 텍스트 비교(&T)",  self._add_text_tab,   "Ctrl+T")
        self._add_action(file_menu, "새 폴더 비교(&D)",    self._add_folder_tab, "Ctrl+D")
        self._add_action(file_menu, "새 3-Way Merge(&M)",  self._add_merge_tab,  "Ctrl+M")
        self._add_action(file_menu, "새 이미지 비교(&I)",  self._add_image_tab,  "Ctrl+I")
        self._add_action(file_menu, "새 바이너리 비교(&B)", self._add_binary_tab, "Ctrl+B")
        self._add_action(file_menu, "Git 비교(&G)",        self._add_git_tab,    "Ctrl+G")
        file_menu.addSeparator()
        self._add_action(file_menu, "SFTP 원격 비교...",   self._open_ftp)
        file_menu.addSeparator()

        # 최근 파일
        self._recent_menu = file_menu.addMenu("최근 비교(&R)")
        self._refresh_recent_menu()

        file_menu.addSeparator()
        self._add_action(file_menu, "세션 저장(&S)", self._save_session_manual, "Ctrl+Shift+W")
        self._add_action(file_menu, "세션 불러오기", self._restore_session)
        file_menu.addSeparator()
        self._add_action(file_menu, "종료(&Q)", self.close, "Ctrl+Q")

        # ── 보기 메뉴 ─────────────────────────────────────
        view_menu = mb.addMenu("보기(&V)")
        self._add_action(view_menu, "다음 변경사항",  self._next_diff,  "F7")
        self._add_action(view_menu, "이전 변경사항",  self._prev_diff,  "Shift+F7")
        view_menu.addSeparator()
        self._add_action(view_menu, "탭 이름 변경",   self._rename_current_tab)
        view_menu.addSeparator()

        # 테마 전환
        act_dark  = QAction("다크 테마", self, checkable=True)
        act_light = QAction("라이트 테마", self, checkable=True)
        if self._cfg.get("theme", "dark") == "dark":
            act_dark.setChecked(True)
        else:
            act_light.setChecked(True)
        act_dark.triggered.connect(lambda: self._switch_theme("dark"))
        act_light.triggered.connect(lambda: self._switch_theme("light"))
        view_menu.addAction(act_dark)
        view_menu.addAction(act_light)

        # ── 도구 메뉴 ─────────────────────────────────────
        tools_menu = mb.addMenu("도구(&T)")
        self._add_action(tools_menu, "설정(&P)...", self._open_settings, "Ctrl+,")

    def _add_action(self, menu, label, slot, shortcut=None):
        act = QAction(label, self)
        if shortcut:
            act.setShortcut(QKeySequence(shortcut))
        act.triggered.connect(slot)
        menu.addAction(act)
        return act

    # ── 탭 관리 ────────────────────────────────────────────

    def _add_text_tab(self, left: str = "", right: str = ""):
        w = TextCompareWidget()
        idx = self._tabs.addTab(w, "텍스트 비교")
        self._tabs.setCurrentIndex(idx)
        if left and right:
            w.load_files(left, right)
            add_recent("text", left, right)
            self._tabs.setTabText(idx, f"{os.path.basename(left)} ↔ {os.path.basename(right)}")
            self._status.showMessage(f"텍스트 비교: {left}")
        return w

    def _add_folder_tab(self, left: str = "", right: str = ""):
        w = FolderCompareWidget()
        w.open_text_compare.connect(self._open_text_compare_from_folder)
        idx = self._tabs.addTab(w, "폴더 비교")
        self._tabs.setCurrentIndex(idx)
        if left and right:
            w.load_folders(left, right)
            add_recent("folder", left, right)
            self._tabs.setTabText(idx, f"📁 {os.path.basename(left)} ↔ {os.path.basename(right)}")
        return w

    def _add_merge_tab(self):
        w = MergeView()
        idx = self._tabs.addTab(w, "3-Way Merge")
        self._tabs.setCurrentIndex(idx)

    def _add_image_tab(self, left: str = "", right: str = ""):
        w = ImageCompareWidget()
        idx = self._tabs.addTab(w, "이미지 비교")
        self._tabs.setCurrentIndex(idx)
        if left and right:
            w.load_files(left, right)
            self._tabs.setTabText(idx, f"🖼 {os.path.basename(left)} ↔ {os.path.basename(right)}")
        return w

    def _add_binary_tab(self, left: str = "", right: str = ""):
        w = BinaryCompareWidget()
        idx = self._tabs.addTab(w, "바이너리 비교")
        self._tabs.setCurrentIndex(idx)
        if left and right:
            w.load_files(left, right)
            self._tabs.setTabText(idx, f"⬡ {os.path.basename(left)} ↔ {os.path.basename(right)}")
        return w

    def _add_git_tab(self):
        w = GitView()
        w.open_text_compare.connect(self._open_text_from_git)
        idx = self._tabs.addTab(w, "Git 비교")
        self._tabs.setCurrentIndex(idx)

    def _close_tab(self, index: int):
        if self._tabs.count() > 1:
            self._tabs.removeTab(index)

    def _open_text_compare_from_folder(self, left: str, right: str):
        w = self._add_text_tab(left, right)

    def _open_text_from_git(self, left_text: str, right_text: str, l_label: str, r_label: str):
        w = TextCompareWidget()
        idx = self._tabs.addTab(w, f"{l_label} ↔ {r_label}")
        self._tabs.setCurrentIndex(idx)
        # git 콘텐츠를 직접 텍스트로 로드
        from core.diff_engine import compute_diff
        left_lines, right_lines, stats = compute_diff(left_text, right_text)
        w._left_ed.set_diff_lines(left_lines)
        w._right_ed.set_diff_lines(right_lines)
        w._compute_diff_blocks(left_lines)
        w._update_stats(stats)
        w._lbl_left.setText(l_label)
        w._lbl_right.setText(r_label)

    # ── FTP ────────────────────────────────────────────────

    def _open_ftp(self):
        dlg = FTPDialog(self)
        dlg.files_selected.connect(self._add_text_tab)
        dlg.exec()

    # ── diff 탐색 단축키 ───────────────────────────────────

    def _current_text_widget(self) -> TextCompareWidget | None:
        w = self._tabs.currentWidget()
        return w if isinstance(w, TextCompareWidget) else None

    def _next_diff(self):
        w = self._current_text_widget()
        if w: w._next_diff()

    def _prev_diff(self):
        w = self._current_text_widget()
        if w: w._prev_diff()

    # ── 탭 이름 변경 ──────────────────────────────────────

    def _rename_tab(self, index: int):
        if index < 0: return
        cur = self._tabs.tabText(index)
        name, ok = QInputDialog.getText(self, "탭 이름 변경", "새 이름:", text=cur)
        if ok and name:
            self._tabs.setTabText(index, name)

    def _rename_current_tab(self):
        self._rename_tab(self._tabs.currentIndex())

    # ── 테마 ──────────────────────────────────────────────

    def _switch_theme(self, name: str):
        set_theme(name)
        self._apply_stylesheet()
        QSettings(SETTINGS_ORG, SETTINGS_APP).setValue("theme", name)

    def _apply_stylesheet(self):
        from ui.text_compare import _THEME, DARK_THEME
        dark = _THEME == DARK_THEME
        bg    = "#1e1e1e" if dark else "#f5f5f5"
        panel = "#252526" if dark else "#ececec"
        fg    = "#d4d4d4" if dark else "#1e1e1e"
        bdr   = "#3c3c3c" if dark else "#c8c8c8"
        sel   = "#094771" if dark else "#0078d4"
        tabsel= "#1e1e1e" if dark else "#ffffff"
        self.setStyleSheet(f"""
            QMainWindow {{ background:{bg}; }}
            QMenuBar {{ background:{panel}; color:{fg}; }}
            QMenuBar::item:selected {{ background:{sel}; color:#fff; }}
            QMenu {{ background:{panel}; color:{fg}; border:1px solid {bdr}; }}
            QMenu::item:selected {{ background:{sel}; color:#fff; }}
            QTabWidget::pane {{ border:none; background:{bg}; }}
            QTabBar::tab {{
                background:#2d2d2d; color:{fg};
                padding:6px 16px; border:1px solid {bdr};
                border-bottom:none; border-radius:3px 3px 0 0;
                min-width:80px;
            }}
            QTabBar::tab:selected {{ background:{tabsel}; color:#ffffff; }}
            QTabBar::tab:hover {{ background:#3a3a3a; }}
            QStatusBar {{ background:#007acc; color:#ffffff; font-size:11px; }}
        """)

    # ── 최근 파일 ──────────────────────────────────────────

    def _refresh_recent_menu(self):
        self._recent_menu.clear()
        recent = load_recent()
        if not recent:
            self._recent_menu.addAction("(없음)").setEnabled(False)
            return
        for entry in recent[:15]:
            t   = entry.get("type", "text")
            lft = entry.get("left", "")
            rgt = entry.get("right", "")
            label = f"[{t}] {os.path.basename(lft)} ↔ {os.path.basename(rgt)}"
            act = QAction(label, self)
            act.setData((t, lft, rgt))
            act.triggered.connect(self._open_recent)
            self._recent_menu.addAction(act)
        self._recent_menu.addSeparator()
        self._recent_menu.addAction("최근 목록 지우기").triggered.connect(
            lambda: (load_recent.__module__ and None) or self._clear_recent()
        )

    def _open_recent(self):
        act: QAction = self.sender()
        t, lft, rgt = act.data()
        if t == "text":
            self._add_text_tab(lft, rgt)
        elif t == "folder":
            self._add_folder_tab(lft, rgt)
        elif t == "image":
            self._add_image_tab(lft, rgt)
        elif t == "binary":
            self._add_binary_tab(lft, rgt)

    def _clear_recent(self):
        from core.session_manager import clear_recent
        clear_recent()
        self._refresh_recent_menu()

    # ── 세션 ───────────────────────────────────────────────

    def _build_session(self) -> AppSession:
        tabs = []
        for i in range(self._tabs.count()):
            w = self._tabs.widget(i)
            info = {}
            if hasattr(w, "get_session_info"):
                info = w.get_session_info()
            if isinstance(w, TextCompareWidget):
                tabs.append(TabSession("text", info.get("left", ""), info.get("right", "")))
            elif isinstance(w, FolderCompareWidget):
                tabs.append(TabSession("folder", info.get("left", ""), info.get("right", "")))
            elif isinstance(w, ImageCompareWidget):
                tabs.append(TabSession("image", info.get("left", ""), info.get("right", "")))
            elif isinstance(w, BinaryCompareWidget):
                tabs.append(TabSession("binary", info.get("left", ""), info.get("right", "")))
        return AppSession(
            tabs=tabs,
            current_tab=self._tabs.currentIndex(),
            window_geometry={"w": self.width(), "h": self.height()},
        )

    def _save_session_manual(self):
        save_session(self._build_session())
        self._status.showMessage("세션 저장됨")

    def _restore_session(self):
        session = load_session()
        if not session or not session.tabs:
            self._status.showMessage("저장된 세션 없음")
            return
        # 기존 탭 제거
        while self._tabs.count() > 0:
            self._tabs.removeTab(0)
        for ts in session.tabs:
            if ts.tab_type == "text":
                self._add_text_tab(ts.left_path, ts.right_path)
            elif ts.tab_type == "folder":
                self._add_folder_tab(ts.left_path, ts.right_path)
            elif ts.tab_type == "image":
                self._add_image_tab(ts.left_path, ts.right_path)
            elif ts.tab_type == "binary":
                self._add_binary_tab(ts.left_path, ts.right_path)
        idx = min(session.current_tab, self._tabs.count() - 1)
        self._tabs.setCurrentIndex(max(0, idx))
        self._status.showMessage("세션 복원됨")

    # ── 레이아웃 저장/복원 ─────────────────────────────────

    def _restore_layout(self):
        qs = QSettings(SETTINGS_ORG, SETTINGS_APP)
        geo = qs.value("geometry")
        if geo:
            self.restoreGeometry(geo)

    def closeEvent(self, event):
        qs = QSettings(SETTINGS_ORG, SETTINGS_APP)
        qs.setValue("geometry", self.saveGeometry())
        if self._cfg.get("restore_session"):
            save_session(self._build_session())
        super().closeEvent(event)

    # ── 설정 ───────────────────────────────────────────────

    def _open_settings(self):
        dlg = SettingsDialog(self)
        dlg.settings_applied.connect(self._on_settings_applied)
        dlg.exec()

    def _on_settings_applied(self, cfg: dict):
        self._cfg = cfg
        set_theme(cfg.get("theme", "dark"))
        self._apply_stylesheet()

    # ── 전역 드래그 앤 드롭 ────────────────────────────────

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        paths = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
        if not paths: return
        # 이미지/바이너리 자동 감지
        img_exts = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"}
        if len(paths) >= 2:
            ext = os.path.splitext(paths[0])[1].lower()
            if ext in img_exts:
                self._add_image_tab(paths[0], paths[1])
            elif os.path.isdir(paths[0]):
                self._add_folder_tab(paths[0], paths[1])
            else:
                self._add_text_tab(paths[0], paths[1])
        elif len(paths) == 1:
            if os.path.isdir(paths[0]):
                self._add_folder_tab(paths[0])
            else:
                self._add_text_tab(paths[0])
