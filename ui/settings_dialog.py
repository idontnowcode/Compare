"""설정 다이얼로그 (폰트, 색상, 테마)."""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QSpinBox, QPushButton, QDialogButtonBox, QGroupBox,
    QFormLayout, QCheckBox, QColorDialog, QFontDialog
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtCore import QSettings
from PyQt6.QtGui import QFont, QColor

from ui.text_compare import set_theme, DARK_THEME, LIGHT_THEME, _THEME


class ColorButton(QPushButton):
    """색상 선택 버튼."""
    color_changed = pyqtSignal(QColor)

    def __init__(self, color: QColor):
        super().__init__()
        self._color = color
        self._update_bg()
        self.clicked.connect(self._pick)

    def _pick(self):
        c = QColorDialog.getColor(self._color, self)
        if c.isValid():
            self._color = c
            self._update_bg()
            self.color_changed.emit(c)

    def _update_bg(self):
        self.setStyleSheet(
            f"background:{self._color.name()}; border:1px solid #555; min-width:60px; min-height:20px;"
        )

    def color(self) -> QColor:
        return self._color


SETTINGS_KEY = "CompareApp"


class SettingsDialog(QDialog):
    settings_applied = pyqtSignal(dict)   # {"theme": str, "font_family": str, "font_size": int, ...}

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("설정")
        self.resize(420, 350)
        self._qs = QSettings(SETTINGS_KEY, "Settings")
        self._setup_ui()
        self._load()

    def _setup_ui(self):
        root = QVBoxLayout(self)

        # 테마
        grp_theme = QGroupBox("테마")
        fl = QFormLayout(grp_theme)
        self._cmb_theme = QComboBox()
        self._cmb_theme.addItems(["다크 (Dark)", "라이트 (Light)"])
        fl.addRow("테마:", self._cmb_theme)
        root.addWidget(grp_theme)

        # 폰트
        grp_font = QGroupBox("폰트")
        fl2 = QFormLayout(grp_font)
        self._lbl_font = QLabel("Consolas 10")
        btn_font = QPushButton("폰트 선택...")
        btn_font.clicked.connect(self._pick_font)
        fl2.addRow("편집기 폰트:", self._lbl_font)
        fl2.addRow("", btn_font)
        root.addWidget(grp_font)
        self._font_family = "Consolas"
        self._font_size   = 10

        # diff 색상
        grp_color = QGroupBox("Diff 색상")
        fl3 = QFormLayout(grp_color)
        self._color_insert  = ColorButton(QColor("#1a3d1a"))
        self._color_delete  = ColorButton(QColor("#3d1a1a"))
        self._color_replace = ColorButton(QColor("#3d3010"))
        fl3.addRow("삽입 배경:", self._color_insert)
        fl3.addRow("삭제 배경:", self._color_delete)
        fl3.addRow("변경 배경:", self._color_replace)
        root.addWidget(grp_color)

        # 기타
        grp_misc = QGroupBox("기타")
        fl4 = QFormLayout(grp_misc)
        self._chk_restore = QCheckBox("시작 시 마지막 세션 복원")
        fl4.addRow("", self._chk_restore)
        root.addWidget(grp_misc)

        # 버튼
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel |
            QDialogButtonBox.StandardButton.Apply
        )
        btns.accepted.connect(self._apply_and_close)
        btns.rejected.connect(self.reject)
        btns.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self._apply)
        root.addWidget(btns)

    def _pick_font(self):
        font = QFont(self._font_family, self._font_size)
        ok, new_font = QFontDialog.getFont(font, self)
        if ok:
            self._font_family = new_font.family()
            self._font_size   = new_font.pointSize()
            self._lbl_font.setText(f"{self._font_family} {self._font_size}")

    def _collect(self) -> dict:
        return {
            "theme":        "dark" if self._cmb_theme.currentIndex() == 0 else "light",
            "font_family":  self._font_family,
            "font_size":    self._font_size,
            "color_insert": self._color_insert.color().name(),
            "color_delete": self._color_delete.color().name(),
            "color_replace": self._color_replace.color().name(),
            "restore_session": self._chk_restore.isChecked(),
        }

    def _apply(self):
        cfg = self._collect()
        self._save(cfg)
        set_theme(cfg["theme"])
        self.settings_applied.emit(cfg)

    def _apply_and_close(self):
        self._apply(); self.accept()

    def _save(self, cfg: dict):
        for k, v in cfg.items():
            self._qs.setValue(k, v)

    def _load(self):
        theme = self._qs.value("theme", "dark")
        self._cmb_theme.setCurrentIndex(0 if theme == "dark" else 1)
        self._font_family = self._qs.value("font_family", "Consolas")
        self._font_size   = int(self._qs.value("font_size", 10))
        self._lbl_font.setText(f"{self._font_family} {self._font_size}")
        if ci := self._qs.value("color_insert"):
            self._color_insert._color = QColor(ci); self._color_insert._update_bg()
        if cd := self._qs.value("color_delete"):
            self._color_delete._color = QColor(cd); self._color_delete._update_bg()
        if cr := self._qs.value("color_replace"):
            self._color_replace._color = QColor(cr); self._color_replace._update_bg()
        self._chk_restore.setChecked(self._qs.value("restore_session", False, type=bool))


def load_settings() -> dict:
    qs = QSettings(SETTINGS_KEY, "Settings")
    return {
        "theme":           qs.value("theme", "dark"),
        "font_family":     qs.value("font_family", "Consolas"),
        "font_size":       int(qs.value("font_size", 10)),
        "restore_session": qs.value("restore_session", False, type=bool),
    }
