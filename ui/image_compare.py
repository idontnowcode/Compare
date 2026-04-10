"""이미지 파일 비교 뷰 (픽셀 diff)."""
import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSplitter,
    QPushButton, QToolBar, QFileDialog, QScrollArea,
    QSlider, QCheckBox, QMessageBox
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QPixmap, QImage, QPainter, QColor

try:
    from PIL import Image, ImageChops, ImageEnhance
    import io
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


class ZoomableImageLabel(QLabel):
    def __init__(self):
        super().__init__()
        self._pixmap_orig: QPixmap | None = None
        self._zoom = 1.0
        self.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.setMinimumSize(100, 100)

    def set_pixmap(self, pm: QPixmap):
        self._pixmap_orig = pm
        self._apply_zoom()

    def set_zoom(self, zoom: float):
        self._zoom = zoom
        self._apply_zoom()

    def _apply_zoom(self):
        if self._pixmap_orig is None:
            return
        w = int(self._pixmap_orig.width()  * self._zoom)
        h = int(self._pixmap_orig.height() * self._zoom)
        scaled = self._pixmap_orig.scaled(
            w, h,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.FastTransformation,
        )
        self.setPixmap(scaled)
        self.resize(scaled.size())


class ImageCompareWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._left_path  = ""
        self._right_path = ""
        self._zoom = 1.0
        self._setup_ui()
        self.setAcceptDrops(True)

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_toolbar())

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self._left_scroll  = self._make_scroll()
        self._right_scroll = self._make_scroll()
        self._diff_scroll  = self._make_scroll()

        self._left_lbl  = ZoomableImageLabel()
        self._right_lbl = ZoomableImageLabel()
        self._diff_lbl  = ZoomableImageLabel()

        for scroll, lbl, title in [
            (self._left_scroll,  self._left_lbl,  "왼쪽"),
            (self._right_scroll, self._right_lbl, "오른쪽"),
            (self._diff_scroll,  self._diff_lbl,  "차이"),
        ]:
            container = QWidget()
            vl = QVBoxLayout(container)
            vl.setContentsMargins(0, 0, 0, 0)
            vl.setSpacing(0)
            hdr = QLabel(title)
            hdr.setFixedHeight(22)
            hdr.setAlignment(Qt.AlignmentFlag.AlignCenter)
            hdr.setStyleSheet("background:#252526; color:#d4d4d4; font-weight:bold;")
            vl.addWidget(hdr)
            scroll.setWidget(lbl)
            vl.addWidget(scroll)
            splitter.addWidget(container)

        root.addWidget(splitter)
        root.addWidget(self._build_status_bar())
        self._apply_stylesheet()

    def _make_scroll(self) -> QScrollArea:
        s = QScrollArea()
        s.setWidgetResizable(False)
        s.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        return s

    def _build_toolbar(self) -> QToolBar:
        tb = QToolBar(); tb.setMovable(False)
        for label, slot in [
            ("왼쪽 이미지 열기",  self._open_left),
            ("오른쪽 이미지 열기", self._open_right),
        ]:
            b = QPushButton(label); b.clicked.connect(slot); tb.addWidget(b)

        tb.addSeparator()
        tb.addWidget(QLabel("확대:"))
        self._zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self._zoom_slider.setRange(10, 400)
        self._zoom_slider.setValue(100)
        self._zoom_slider.setFixedWidth(120)
        self._zoom_slider.valueChanged.connect(self._on_zoom)
        tb.addWidget(self._zoom_slider)
        self._lbl_zoom = QLabel("100%")
        tb.addWidget(self._lbl_zoom)
        return tb

    def _build_status_bar(self) -> QWidget:
        w = QWidget(); w.setFixedHeight(24)
        lay = QHBoxLayout(w); lay.setContentsMargins(8, 0, 8, 0)
        self._lbl_info = QLabel("")
        lay.addWidget(self._lbl_info)
        lay.addStretch()
        return w

    def _apply_stylesheet(self):
        self.setStyleSheet("""
            QWidget { background:#1e1e1e; color:#d4d4d4; }
            QPushButton { background:#2d2d2d; color:#d4d4d4; border:1px solid #3c3c3c; padding:3px 8px; border-radius:3px; }
            QPushButton:hover { background:#3a3a3a; }
            QToolBar { background:#252526; border-bottom:1px solid #3c3c3c; spacing:4px; padding:2px; }
            QLabel { color:#d4d4d4; padding:0 4px; }
            QScrollArea { background:#2a2a2a; border:none; }
        """)

    def _open_left(self):
        p, _ = QFileDialog.getOpenFileName(
            self, "왼쪽 이미지 선택", "",
            "이미지 (*.png *.jpg *.jpeg *.bmp *.gif *.webp)"
        )
        if p: self._left_path = p; self._refresh()

    def _open_right(self):
        p, _ = QFileDialog.getOpenFileName(
            self, "오른쪽 이미지 선택", "",
            "이미지 (*.png *.jpg *.jpeg *.bmp *.gif *.webp)"
        )
        if p: self._right_path = p; self._refresh()

    def load_files(self, left: str, right: str):
        self._left_path = left; self._right_path = right; self._refresh()

    def _refresh(self):
        if not PIL_AVAILABLE:
            self._lbl_info.setText("Pillow 라이브러리가 필요합니다: pip install Pillow")
            return

        def load_pm(path: str) -> QPixmap | None:
            try:
                img = Image.open(path).convert("RGBA")
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                qimg = QImage.fromData(buf.getvalue())
                return QPixmap.fromImage(qimg)
            except Exception:
                return None

        pm_left  = load_pm(self._left_path)  if self._left_path  else None
        pm_right = load_pm(self._right_path) if self._right_path else None

        if pm_left:
            self._left_lbl.set_pixmap(pm_left)
        if pm_right:
            self._right_lbl.set_pixmap(pm_right)

        # diff 이미지 생성
        if pm_left and pm_right and self._left_path and self._right_path:
            try:
                img_l = Image.open(self._left_path).convert("RGBA")
                img_r = Image.open(self._right_path).convert("RGBA")

                # 크기 맞추기
                if img_l.size != img_r.size:
                    img_r = img_r.resize(img_l.size, Image.LANCZOS)

                diff = ImageChops.difference(img_l, img_r)
                enhanced = ImageEnhance.Brightness(diff).enhance(5.0)
                buf = io.BytesIO()
                enhanced.save(buf, format="PNG")
                pm_diff = QPixmap.fromImage(QImage.fromData(buf.getvalue()))
                self._diff_lbl.set_pixmap(pm_diff)

                # 통계
                import struct
                data = list(diff.getdata())
                diff_pixels = sum(1 for r, g, b, a in data if r or g or b)
                total = img_l.width * img_l.height
                pct = diff_pixels / total * 100 if total else 0
                self._lbl_info.setText(
                    f"크기: {img_l.width}×{img_l.height} | "
                    f"다른 픽셀: {diff_pixels:,} / {total:,} ({pct:.1f}%)"
                )
            except Exception as e:
                self._lbl_info.setText(f"diff 실패: {e}")

    def _on_zoom(self, value: int):
        self._zoom = value / 100.0
        self._lbl_zoom.setText(f"{value}%")
        for lbl in (self._left_lbl, self._right_lbl, self._diff_lbl):
            lbl.set_zoom(self._zoom)

    # 드래그 앤 드롭
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls(): event.acceptProposedAction()

    def dropEvent(self, event):
        paths = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
        if len(paths) >= 2:
            self.load_files(paths[0], paths[1])
        elif len(paths) == 1:
            self._left_path = paths[0]; self._refresh()

    def get_session_info(self) -> dict:
        return {"left": self._left_path, "right": self._right_path}
