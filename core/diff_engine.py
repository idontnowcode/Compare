import difflib
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class LineType(Enum):
    EQUAL   = "equal"
    INSERT  = "insert"
    DELETE  = "delete"
    REPLACE = "replace"
    EMPTY   = "empty"


@dataclass
class InlineSpan:
    """문자/단어 단위 인라인 diff 범위."""
    start: int
    length: int
    is_changed: bool   # True=변경됨, False=동일


@dataclass
class DiffLine:
    line_no: Optional[int]
    text: str
    line_type: LineType
    inline_spans: list[InlineSpan] = field(default_factory=list)


@dataclass
class DiffStats:
    total_lines: int
    added: int
    deleted: int
    changed: int

    @property
    def identical(self) -> int:
        return self.total_lines - self.added - self.deleted - self.changed


def _char_inline_spans(left: str, right: str) -> tuple[list[InlineSpan], list[InlineSpan]]:
    """두 문자열 간 문자 단위 diff → 각각의 InlineSpan 리스트."""
    sm = difflib.SequenceMatcher(None, left, right, autojunk=False)
    left_spans: list[InlineSpan] = []
    right_spans: list[InlineSpan] = []

    prev_li = prev_ri = 0
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            if i2 > i1:
                left_spans.append(InlineSpan(i1, i2 - i1, False))
            if j2 > j1:
                right_spans.append(InlineSpan(j1, j2 - j1, False))
        else:
            if i2 > i1:
                left_spans.append(InlineSpan(i1, i2 - i1, True))
            if j2 > j1:
                right_spans.append(InlineSpan(j1, j2 - j1, True))

    return left_spans, right_spans


def _word_inline_spans(left: str, right: str) -> tuple[list[InlineSpan], list[InlineSpan]]:
    """단어 단위 diff → InlineSpan 리스트."""
    def tokenize(s: str) -> list[str]:
        tokens = []
        cur = ""
        for ch in s:
            if ch in " \t":
                if cur:
                    tokens.append(cur)
                    cur = ""
                tokens.append(ch)
            else:
                cur += ch
        if cur:
            tokens.append(cur)
        return tokens

    left_tokens = tokenize(left)
    right_tokens = tokenize(right)

    sm = difflib.SequenceMatcher(None, left_tokens, right_tokens, autojunk=False)

    def build_spans(tokens: list[str], opcodes, side: str) -> list[InlineSpan]:
        spans = []
        pos = 0
        lengths = [len(t) for t in tokens]
        offsets = []
        cur = 0
        for l in lengths:
            offsets.append(cur)
            cur += l

        for tag, i1, i2, j1, j2 in opcodes:
            if side == "left":
                idx1, idx2 = i1, i2
            else:
                idx1, idx2 = j1, j2

            if idx2 > idx1:
                start = offsets[idx1] if idx1 < len(offsets) else cur
                end = offsets[idx2 - 1] + lengths[idx2 - 1] if idx2 - 1 < len(offsets) else cur
                is_changed = tag != "equal"
                spans.append(InlineSpan(start, end - start, is_changed))

        return spans

    opcodes = sm.get_opcodes()
    left_spans = build_spans(left_tokens, opcodes, "left")
    right_spans = build_spans(right_tokens, opcodes, "right")
    return left_spans, right_spans


def compute_diff(
    left_text: str,
    right_text: str,
    inline_mode: str = "char",   # "char" | "word" | "none"
) -> tuple[list[DiffLine], list[DiffLine], DiffStats]:
    left_lines = left_text.splitlines(keepends=True)
    right_lines = right_text.splitlines(keepends=True)

    matcher = difflib.SequenceMatcher(None, left_lines, right_lines, autojunk=False)
    opcodes = matcher.get_opcodes()

    left_result: list[DiffLine] = []
    right_result: list[DiffLine] = []

    left_no = right_no = 1
    stats = DiffStats(total_lines=0, added=0, deleted=0, changed=0)

    for tag, i1, i2, j1, j2 in opcodes:
        left_chunk  = left_lines[i1:i2]
        right_chunk = right_lines[j1:j2]

        if tag == "equal":
            for line in left_chunk:
                t = line.rstrip("\n")
                left_result.append(DiffLine(left_no, t, LineType.EQUAL))
                right_result.append(DiffLine(right_no, t, LineType.EQUAL))
                left_no += 1; right_no += 1
            stats.total_lines += len(left_chunk)

        elif tag == "replace":
            max_len = max(len(left_chunk), len(right_chunk))
            stats.changed += max_len
            stats.total_lines += max_len
            for i in range(max_len):
                lt = left_chunk[i].rstrip("\n")  if i < len(left_chunk)  else ""
                rt = right_chunk[i].rstrip("\n") if i < len(right_chunk) else ""

                if inline_mode == "char":
                    l_spans, r_spans = _char_inline_spans(lt, rt)
                elif inline_mode == "word":
                    l_spans, r_spans = _word_inline_spans(lt, rt)
                else:
                    l_spans, r_spans = [], []

                if i < len(left_chunk):
                    left_result.append(DiffLine(left_no, lt, LineType.REPLACE, l_spans))
                    left_no += 1
                else:
                    left_result.append(DiffLine(None, "", LineType.EMPTY))

                if i < len(right_chunk):
                    right_result.append(DiffLine(right_no, rt, LineType.REPLACE, r_spans))
                    right_no += 1
                else:
                    right_result.append(DiffLine(None, "", LineType.EMPTY))

        elif tag == "delete":
            stats.deleted += len(left_chunk)
            stats.total_lines += len(left_chunk)
            for line in left_chunk:
                left_result.append(DiffLine(left_no, line.rstrip("\n"), LineType.DELETE))
                right_result.append(DiffLine(None, "", LineType.EMPTY))
                left_no += 1

        elif tag == "insert":
            stats.added += len(right_chunk)
            stats.total_lines += len(right_chunk)
            for line in right_chunk:
                left_result.append(DiffLine(None, "", LineType.EMPTY))
                right_result.append(DiffLine(right_no, line.rstrip("\n"), LineType.INSERT))
                right_no += 1

    return left_result, right_result, stats
