import os
import re
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QSplitter,
    QPushButton, QToolBar, QFileDialog, QPlainTextEdit,
    QTextEdit, QFrame, QSizePolicy, QCheckBox, QComboBox,
    QLineEdit, QMessageBox, QScrollBar
)
from PyQt6.QtCore import (
    Qt, QRect, QSize, pyqtSignal, QTimer, QRegularExpression
)
from PyQt6.QtGui import (
    QPainter, QColor, QFont, QFontMetrics, QTextCharFormat,
    QSyntaxHighlighter, QTextCursor, QTextDocument, QTextOption,
    QPen, QKeySequence
)

from core.diff_engine import compute_diff, LineType, DiffLine, InlineSpan, DiffStats

# ── 색상 ──────────────────────────────────────────────────

DARK_THEME = {
    "bg":            QColor("#1e1e1e"),
    "text":          QColor("#d4d4d4"),
    "lineno_bg":     QColor("#252526"),
    "lineno_fg":     QColor("#858585"),
    "border":        QColor("#3c3c3c"),
    LineType.EQUAL:   QColor("#1e1e1e"),
    LineType.INSERT:  QColor("#1a3d1a"),
    LineType.DELETE:  QColor("#3d1a1a"),
    LineType.REPLACE: QColor("#3d3010"),
    LineType.EMPTY:   QColor("#2a2a2a"),
    "inline_changed": QColor(255, 200, 0, 80),
    "search_hl":      QColor("#515c6a"),
    "search_cur":     QColor("#ea700d"),
    "current_diff":   QColor(255, 255, 255, 20),
}

LIGHT_THEME = {
    "bg":            QColor("#ffffff"),
    "text":          QColor("#1e1e1e"),
    "lineno_bg":     QColor("#f3f3f3"),
    "lineno_fg":     QColor("#999999"),
    "border":        QColor("#d0d0d0"),
    LineType.EQUAL:   QColor("#ffffff"),
    LineType.INSERT:  QColor("#d4edda"),
    LineType.DELETE:  QColor("#f8d7da"),
    LineType.REPLACE: QColor("#fff3cd"),
    LineType.EMPTY:   QColor("#f5f5f5"),
    "inline_changed": QColor(200, 150, 0, 80),
    "search_hl":      QColor("#b8d6fb"),
    "search_cur":     QColor("#ffa500"),
    "current_diff":   QColor(0, 0, 0, 15),
}

_THEME = DARK_THEME


def set_theme(name: str):
    global _THEME
    _THEME = DARK_THEME if name == "dark" else LIGHT_THEME


# ── LineNumberArea ────────────────────────────────────────

class LineNumberArea(QWidget):
    WIDTH = 52

    def __init__(self, editor: "DiffEditor"):
        super().__init__(editor)
        self._editor = editor
        self.setFixedWidth(self.WIDTH)

    def paintEvent(self, event):
        self._editor.paint_line_numbers(self)


# ── DiffHighlighter ───────────────────────────────────────

class DiffHighlighter(QSyntaxHighlighter):
    def __init__(self, doc: QTextDocument):
        super().__init__(doc)
        self._diff_lines: list[DiffLine] = []

    def set_diff_lines(self, diff_lines: list[DiffLine]):
        self._diff_lines = diff_lines
        self.rehighlight()

    def highlightBlock(self, text: str):
        block_num = self.currentBlock().blockNumber()
        if block_num >= len(self._diff_lines):
            return
        line = self._diff_lines[block_num]
        if line.line_type == LineType.EQUAL:
            return

        bg = _THEME.get(line.line_type, _THEME[LineType.EQUAL])
        base_fmt = QTextCharFormat()
        base_fmt.setBackground(bg)
        self.setFormat(0, len(text), base_fmt)

        # 인라인 스팬
        for span in line.inline_spans:
            if span.is_changed:
                fmt = QTextCharFormat()
                fmt.setBackground(_THEME["inline_changed"])
                self.setFormat(span.start, span.length, fmt)


# ── DiffEditor ────────────────────────────────────────────

class DiffEditor(QPlainTextEdit):
    scrolled = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._diff_lines: list[DiffLine] = []
        self._current_diff_rows: set[int] = set()

        font = QFont("Consolas", 10)
        if QFontMetrics(font).horizontalAdvance("A") == 0:
            font = QFont("Monospace", 10)
        self.setFont(font)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.setReadOnly(True)

        self._line_area = LineNumberArea(self)
        self._highlighter = DiffHighlighter(self.document())

        self.blockCountChanged.connect(self._update_line_area_width)
        self.updateRequest.connect(self._update_line_area)
        self.verticalScrollBar().valueChanged.connect(self.scrolled.emit)
        self._update_line_area_width()

    # ── 라인 번호 ─────────────────────────────────────────

    def _update_line_area_width(self):
        self.setViewportMargins(LineNumberArea.WIDTH, 0, 0, 0)

    def _update_line_area(self, rect, dy):
        if dy:
            self._line_area.scroll(0, dy)
        else:
            self._line_area.update(0, rect.y(), self._line_area.width(), rect.height())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self._line_area.setGeometry(QRect(cr.left(), cr.top(), LineNumberArea.WIDTH, cr.height()))

    def paint_line_numbers(self, area: LineNumberArea):
        painter = QPainter(area)
        painter.fillRect(area.rect(), _THEME["lineno_bg"])
        painter.setPen(QPen(_THEME["border"]))
        painter.drawLine(area.width() - 1, 0, area.width() - 1, area.height())

        block = self.firstVisibleBlock()
        block_num = block.blockNumber()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())

        fm = QFontMetrics(self.font())
        line_height = fm.height() + 2

        while block.isValid() and top <= area.rect().bottom():
            if block.isVisible() and bottom >= area.rect().top():
                # 현재 diff 블록 강조
                if block_num in self._current_diff_rows:
                    painter.fillRect(0, top, area.width() - 1, line_height, _THEME["current_diff"])

                # 라인 번호 표시
                lno = None
                if block_num < len(self._diff_lines):
                    lno = self._diff_lines[block_num].line_no
                if lno is not None:
                    painter.setPen(_THEME["lineno_fg"])
                    painter.drawText(
                        QRect(0, top, area.width() - 6, line_height),
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                        str(lno)
                    )

            block = block.next()
            block_num += 1
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())

        painter.end()

    # ── diff 데이터 설정 ──────────────────────────────────

    def set_diff_lines(self, diff_lines: list[DiffLine]):
        self._diff_lines = diff_lines
        content = "\n".join(line.text for line in diff_lines)
        self.setPlainText(content)
        self._highlighter.set_diff_lines(diff_lines)
        self._update_empty_line_bg()

    def _update_empty_line_bg(self):
        """EMPTY 타입 블록 배경 extra selection으로 처리."""
        extra = []
        block = self.document().begin()
        block_num = 0
        while block.isValid():
            if block_num < len(self._diff_lines):
                lt = self._diff_lines[block_num].line_type
                if lt in (LineType.EMPTY,):
                    sel = QTextEdit.ExtraSelection()
                    sel.format.setBackground(_THEME[LineType.EMPTY])
                    sel.format.setProperty(
                        QTextCharFormat.Property.FullWidthSelection, True
                    )
                    cur = QTextCursor(block)
                    sel.cursor = cur
                    extra.append(sel)
            block = block.next()
            block_num += 1
        self.setExtraSelections(extra)

    def set_current_diff_rows(self, rows: set[int]):
        self._current_diff_rows = rows
        self._line_area.update()

    def scroll_to_block(self, block_num: int):
        block = self.document().findBlockByNumber(block_num)
        if block.isValid():
            cur = QTextCursor(block)
            self.setTextCursor(cur)
            self.centerCursor()

    def sync_scroll(self, value: int):
        self.verticalScrollBar().setValue(value)

    # ── 편집 모드 ─────────────────────────────────────────

    def set_editable(self, editable: bool):
        self.setReadOnly(not editable)

    def get_text(self) -> str:
        return self.toPlainText()

    def set_text(self, text: str):
        self.setPlainText(text)

    # ── 검색 하이라이트 ───────────────────────────────────

    def highlight_search(self, pattern: str, use_regex: bool, case_sensitive: bool) -> int:
        """검색어 강조. 매칭 개수 반환."""
        extra = list(self.extraSelections())
        # 이전 검색 결과 제거 (EMPTY bg 유지)
        extra = [e for e in extra if e.format.background().color() != _THEME["search_hl"]]

        if not pattern:
            self.setExtraSelections(extra)
            return 0

        flags = QTextDocument.FindFlag(0)
        if case_sensitive:
            flags |= QTextDocument.FindFlag.FindCaseSensitively

        count = 0
        doc = self.document()
        if use_regex:
            try:
                regex = QRegularExpression(pattern)
                if not case_sensitive:
                    regex.setPatternOptions(
                        QRegularExpression.PatternOption.CaseInsensitiveOption
                    )
                cur = doc.find(regex)
            except Exception:
                return 0
        else:
            cur = doc.find(pattern, 0, flags)

        while not cur.isNull():
            sel = QTextEdit.ExtraSelection()
            sel.format.setBackground(_THEME["search_hl"])
            sel.cursor = cur
            extra.append(sel)
            count += 1
            if use_regex:
                cur = doc.find(regex, cur)
            else:
                cur = doc.find(pattern, cur, flags)

        self.setExtraSelections(extra)
        return count

    def go_to_next_match(self, pattern: str, use_regex: bool, case_sensitive: bool):
        flags = QTextDocument.FindFlag(0)
        if case_sensitive:
            flags |= QTextDocument.FindFlag.FindCaseSensitively
        doc = self.document()
        start_cur = self.textCursor()
        if use_regex:
            regex = QRegularExpression(pattern)
            if not case_sensitive:
                regex.setPatternOptions(
                    QRegularExpression.PatternOption.CaseInsensitiveOption
                )
            cur = doc.find(regex, start_cur)
            if cur.isNull():
                cur = doc.find(regex)
        else:
            cur = doc.find(pattern, start_cur, flags)
            if cur.isNull():
                cur = doc.find(pattern, 0, flags)
        if not cur.isNull():
            self.setTextCursor(cur)
            self.centerCursor()


# ── SearchBar ────────────────────────────────────────────

class SearchBar(QWidget):
    search_changed = pyqtSignal(str, bool, bool)  # (pattern, use_regex, case_sensitive)
    find_next      = pyqtSignal()
    closed         = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self.hide()

    def _setup_ui(self):
        lay = QHBoxLayout(self)
        lay.setContentsMargins(6, 2, 6, 2)
        lay.setSpacing(4)

        self._input = QLineEdit()
        self._input.setPlaceholderText("검색 (Ctrl+F)")
        self._input.setFixedWidth(200)
        self._input.textChanged.connect(self._emit_search)
        self._input.returnPressed.connect(self.find_next.emit)

        self._chk_regex = QCheckBox("정규식")
        self._chk_case  = QCheckBox("대소문자")
        self._lbl_count = QLabel("")
        self._btn_next  = QPushButton("▼")
        self._btn_prev  = QPushButton("▲")
        self._btn_close = QPushButton("✕")
        self._btn_next.setFixedSize(24, 24)
        self._btn_prev.setFixedSize(24, 24)
        self._btn_close.setFixedSize(24, 24)

        self._chk_regex.stateChanged.connect(self._emit_search)
        self._chk_case.stateChanged.connect(self._emit_search)
        self._btn_next.clicked.connect(self.find_next.emit)
        self._btn_close.clicked.connect(self._close)

        for w in [QLabel("찾기:"), self._input, self._chk_regex, self._chk_case,
                  self._btn_prev, self._btn_next, self._lbl_count, self._btn_close]:
            lay.addWidget(w)
        lay.addStretch()

    def _emit_search(self):
        self.search_changed.emit(
            self._input.text(),
            self._chk_regex.isChecked(),
            self._chk_case.isChecked(),
        )

    def _close(self):
        self.hide()
        self.closed.emit()

    def open(self):
        self.show()
        self._input.setFocus()
        self._input.selectAll()

    def set_count(self, n: int):
        self._lbl_count.setText(f"{n}개" if n else "없음")

    def pattern(self) -> str:
        return self._input.text()

    def use_regex(self) -> bool:
        return self._chk_regex.isChecked()

    def case_sensitive(self) -> bool:
        return self._chk_case.isChecked()


# ── TextCompareWidget ─────────────────────────────────────

class TextCompareWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._left_path  = ""
        self._right_path = ""
        self._left_orig  = ""   # 파일에서 읽은 원본
        self._right_orig = ""
        self._diff_blocks: list[int] = []   # diff 시작 블록 번호
        self._current_diff = 0
        self._inline_mode = "char"          # "char" | "word" | "none"
        self._edit_mode = False
        self._debounce = QTimer()
        self._debounce.setSingleShot(True)
        self._debounce.timeout.connect(self._refresh_diff)
        self._setup_ui()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_toolbar())
        root.addWidget(self._build_path_header())

        self._search_bar = SearchBar()
        self._search_bar.search_changed.connect(self._on_search_changed)
        self._search_bar.find_next.connect(self._on_find_next)
        self._search_bar.closed.connect(self._clear_search)
        root.addWidget(self._search_bar)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self._left_ed  = DiffEditor()
        self._right_ed = DiffEditor()
        splitter.addWidget(self._left_ed)
        splitter.addWidget(self._right_ed)
        splitter.setSizes([1, 1])
        root.addWidget(splitter)

        root.addWidget(self._build_stats_bar())

        # 스크롤 동기화
        self._left_ed.scrolled.connect(self._right_ed.sync_scroll)
        self._right_ed.scrolled.connect(self._left_ed.sync_scroll)

        # 편집 시 diff 재계산 (디바운스)
        self._left_ed.textChanged.connect(lambda: self._debounce.start(500))
        self._right_ed.textChanged.connect(lambda: self._debounce.start(500))

        self._apply_stylesheet()

    # ── 툴바 ─────────────────────────────────────────────

    def _build_toolbar(self) -> QToolBar:
        tb = QToolBar(); tb.setMovable(False)

        def btn(label, slot, shortcut=None):
            b = QPushButton(label)
            b.clicked.connect(slot)
            if shortcut:
                b.setShortcut(QKeySequence(shortcut))
            tb.addWidget(b)
            return b

        btn("왼쪽 열기",  self._open_left)
        btn("오른쪽 열기", self._open_right)
        tb.addSeparator()
        self._btn_edit = btn("편집 모드", self._toggle_edit)
        self._btn_edit.setCheckable(True)
        btn("저장(좌)", self._save_left,  "Ctrl+Shift+S")
        btn("저장(우)", self._save_right)
        tb.addSeparator()
        btn("◀ 이전", self._prev_diff, "Shift+F7")
        btn("다음 ▶", self._next_diff, "F7")
        self._lbl_pos = QLabel("0 / 0"); tb.addWidget(self._lbl_pos)
        tb.addSeparator()
        btn("← 복사", self._copy_right_to_left)
        btn("복사 →", self._copy_left_to_right)
        tb.addSeparator()

        # 인라인 모드
        tb.addWidget(QLabel("인라인:"))
        self._cmb_inline = QComboBox()
        self._cmb_inline.addItems(["문자", "단어", "없음"])
        self._cmb_inline.currentIndexChanged.connect(self._on_inline_mode_change)
        tb.addWidget(self._cmb_inline)
        tb.addSeparator()

        btn("검색(Ctrl+F)", self._open_search, "Ctrl+F")
        return tb

    def _build_path_header(self) -> QWidget:
        w = QWidget(); w.setFixedHeight(28)
        lay = QHBoxLayout(w); lay.setContentsMargins(4, 2, 4, 2)
        self._lbl_left  = QLabel("(파일 없음)")
        self._lbl_right = QLabel("(파일 없음)")
        for lbl in (self._lbl_left, self._lbl_right):
            lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        lay.addWidget(self._lbl_left)
        lay.addWidget(QLabel("↔"))
        lay.addWidget(self._lbl_right)
        return w

    def _build_stats_bar(self) -> QWidget:
        w = QWidget(); w.setFixedHeight(24)
        lay = QHBoxLayout(w); lay.setContentsMargins(8, 0, 8, 0); lay.setSpacing(16)
        self._lbl_added   = QLabel("추가: 0")
        self._lbl_deleted = QLabel("삭제: 0")
        self._lbl_changed = QLabel("변경: 0")
        self._lbl_same    = QLabel("동일: 0")
        for l in (self._lbl_added, self._lbl_deleted, self._lbl_changed, self._lbl_same):
            lay.addWidget(l)
        lay.addStretch()
        return w

    def _apply_stylesheet(self):
        dark = _THEME == DARK_THEME
        bg    = "#1e1e1e" if dark else "#ffffff"
        fg    = "#d4d4d4" if dark else "#1e1e1e"
        panel = "#252526" if dark else "#f3f3f3"
        bdr   = "#3c3c3c" if dark else "#d0d0d0"
        self.setStyleSheet(f"""
            QWidget {{ background:{bg}; color:{fg}; }}
            QPushButton {{
                background:#2d2d2d; color:{fg};
                border:1px solid {bdr}; padding:3px 8px; border-radius:3px;
            }}
            QPushButton:hover {{ background:#3a3a3a; }}
            QPushButton:checked {{ background:#007acc; color:#fff; }}
            QToolBar {{ background:{panel}; border-bottom:1px solid {bdr}; spacing:4px; padding:2px; }}
            QLabel {{ color:{fg}; padding:0 4px; }}
            QComboBox {{ background:#2d2d2d; color:{fg}; border:1px solid {bdr}; padding:2px 4px; }}
            QLineEdit {{ background:#2d2d2d; color:{fg}; border:1px solid {bdr}; padding:2px 4px; border-radius:3px; }}
            QCheckBox {{ color:{fg}; }}
            QSplitter::handle {{ background:{bdr}; width:2px; }}
            QPlainTextEdit {{ background:{bg}; color:{fg}; border:none; }}
        """)

    # ── 파일 열기 ─────────────────────────────────────────

    def _open_left(self):
        p, _ = QFileDialog.getOpenFileName(self, "왼쪽 파일 선택")
        if p:
            self._left_path = p
            self._lbl_left.setText(p)
            self._left_orig = self._read(p)
            self._left_ed.set_text(self._left_orig)
            self._refresh_diff()

    def _open_right(self):
        p, _ = QFileDialog.getOpenFileName(self, "오른쪽 파일 선택")
        if p:
            self._right_path = p
            self._lbl_right.setText(p)
            self._right_orig = self._read(p)
            self._right_ed.set_text(self._right_orig)
            self._refresh_diff()

    def load_files(self, left_path: str, right_path: str):
        self._left_path  = left_path
        self._right_path = right_path
        self._lbl_left.setText(left_path)
        self._lbl_right.setText(right_path)
        self._left_orig  = self._read(left_path)
        self._right_orig = self._read(right_path)
        self._left_ed.set_text(self._left_orig)
        self._right_ed.set_text(self._right_orig)
        self._refresh_diff()

    def _read(self, path: str) -> str:
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                return f.read()
        except OSError:
            return ""

    # ── diff 계산 ─────────────────────────────────────────

    def _refresh_diff(self):
        lt = self._left_ed.get_text()
        rt = self._right_ed.get_text()
        mode = ["char", "word", "none"][self._cmb_inline.currentIndex()]
        left_lines, right_lines, stats = compute_diff(lt, rt, inline_mode=mode)
        self._left_ed.set_diff_lines(left_lines)
        self._right_ed.set_diff_lines(right_lines)
        self._compute_diff_blocks(left_lines)
        self._update_stats(stats)
        self._current_diff = 0
        self._update_pos_label()
        if self._diff_blocks:
            self._highlight_current_diff()

    def _compute_diff_blocks(self, lines: list[DiffLine]):
        self._diff_blocks = []
        prev_equal = True
        for i, line in enumerate(lines):
            is_diff = line.line_type not in (LineType.EQUAL, LineType.EMPTY)
            if is_diff and prev_equal:
                self._diff_blocks.append(i)
            prev_equal = not is_diff

    def _update_stats(self, stats: DiffStats):
        self._lbl_added.setText(f"추가: {stats.added}")
        self._lbl_deleted.setText(f"삭제: {stats.deleted}")
        self._lbl_changed.setText(f"변경: {stats.changed}")
        self._lbl_same.setText(f"동일: {stats.identical}")

    def _update_pos_label(self):
        n = len(self._diff_blocks)
        if n:
            self._lbl_pos.setText(f"{self._current_diff + 1} / {n}")
        else:
            self._lbl_pos.setText("없음")

    def _highlight_current_diff(self):
        if not self._diff_blocks:
            return
        row = self._diff_blocks[self._current_diff]
        rows: set[int] = set()
        for i, line in enumerate(self._left_ed._diff_lines):
            if i >= row and line.line_type not in (LineType.EQUAL,):
                rows.add(i)
            elif i >= row and line.line_type == LineType.EQUAL and rows:
                break
        self._left_ed.set_current_diff_rows(rows)
        self._right_ed.set_current_diff_rows(rows)
        self._left_ed.scroll_to_block(row)
        self._right_ed.scroll_to_block(row)

    # ── diff 탐색 ─────────────────────────────────────────

    def _prev_diff(self):
        if not self._diff_blocks: return
        self._current_diff = (self._current_diff - 1) % len(self._diff_blocks)
        self._update_pos_label()
        self._highlight_current_diff()

    def _next_diff(self):
        if not self._diff_blocks: return
        self._current_diff = (self._current_diff + 1) % len(self._diff_blocks)
        self._update_pos_label()
        self._highlight_current_diff()

    # ── 편집 모드 ─────────────────────────────────────────

    def _toggle_edit(self):
        self._edit_mode = self._btn_edit.isChecked()
        self._left_ed.set_editable(self._edit_mode)
        self._right_ed.set_editable(self._edit_mode)

    # ── 저장 ─────────────────────────────────────────────

    def _save_left(self):
        self._save_panel(self._left_ed, self._left_path, "왼쪽")

    def _save_right(self):
        self._save_panel(self._right_ed, self._right_path, "오른쪽")

    def _save_panel(self, editor: DiffEditor, path: str, side: str):
        if not path:
            path, _ = QFileDialog.getSaveFileName(self, f"{side} 파일 저장")
            if not path:
                return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(editor.get_text())
        except OSError as e:
            QMessageBox.critical(self, "저장 실패", str(e))

    # ── 변경사항 복사 ─────────────────────────────────────

    def _copy_left_to_right(self):
        self._right_ed.set_text(self._left_ed.get_text())
        self._refresh_diff()

    def _copy_right_to_left(self):
        self._left_ed.set_text(self._right_ed.get_text())
        self._refresh_diff()

    # ── 검색 ─────────────────────────────────────────────

    def _open_search(self):
        self._search_bar.open()

    def _on_search_changed(self, pattern: str, use_regex: bool, case_sensitive: bool):
        n1 = self._left_ed.highlight_search(pattern, use_regex, case_sensitive)
        n2 = self._right_ed.highlight_search(pattern, use_regex, case_sensitive)
        self._search_bar.set_count(n1 + n2)

    def _on_find_next(self):
        p = self._search_bar.pattern()
        r = self._search_bar.use_regex()
        c = self._search_bar.case_sensitive()
        self._left_ed.go_to_next_match(p, r, c)
        self._right_ed.go_to_next_match(p, r, c)

    def _clear_search(self):
        self._left_ed.highlight_search("", False, False)
        self._right_ed.highlight_search("", False, False)

    # ── 인라인 모드 변경 ──────────────────────────────────

    def _on_inline_mode_change(self):
        self._refresh_diff()

    # ── 드래그 앤 드롭 ────────────────────────────────────

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        paths = [u.toLocalFile() for u in urls if u.isLocalFile()]
        if len(paths) >= 2:
            self.load_files(paths[0], paths[1])
        elif len(paths) == 1:
            self._left_path = paths[0]
            self._lbl_left.setText(paths[0])
            self._left_orig = self._read(paths[0])
            self._left_ed.set_text(self._left_orig)
            self._refresh_diff()

    def get_session_info(self) -> dict:
        return {"left": self._left_path, "right": self._right_path}
