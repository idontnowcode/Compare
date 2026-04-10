"""3-way merge engine."""
import difflib
from dataclasses import dataclass, field
from enum import Enum


class ChunkType(Enum):
    UNCHANGED  = "unchanged"   # base == left == right
    LEFT_ONLY  = "left_only"   # left changed, right same as base
    RIGHT_ONLY = "right_only"  # right changed, left same as base
    CONFLICT   = "conflict"    # both changed differently
    BOTH_SAME  = "both_same"   # left == right != base


@dataclass
class MergeChunk:
    chunk_type: ChunkType
    base_lines:  list[str] = field(default_factory=list)
    left_lines:  list[str] = field(default_factory=list)
    right_lines: list[str] = field(default_factory=list)
    resolved:    bool = False
    resolved_lines: list[str] = field(default_factory=list)

    @property
    def result_lines(self) -> list[str]:
        if self.chunk_type == ChunkType.UNCHANGED:
            return self.base_lines
        if self.chunk_type == ChunkType.LEFT_ONLY:
            return self.left_lines
        if self.chunk_type == ChunkType.RIGHT_ONLY:
            return self.right_lines
        if self.chunk_type == ChunkType.BOTH_SAME:
            return self.left_lines
        # CONFLICT
        return self.resolved_lines if self.resolved else []


def three_way_merge(
    base_text: str, left_text: str, right_text: str
) -> tuple[list[MergeChunk], bool]:
    """
    Returns (chunks, has_conflict).
    chunks에서 CONFLICT인 항목은 resolved=False.
    """
    base  = base_text.splitlines(keepends=True)
    left  = left_text.splitlines(keepends=True)
    right = right_text.splitlines(keepends=True)

    base_to_left  = difflib.SequenceMatcher(None, base, left,  autojunk=False)
    base_to_right = difflib.SequenceMatcher(None, base, right, autojunk=False)

    # base 라인별 변경 추적
    left_change:  dict[int, list[str]] = {}  # base_idx -> new lines (None=removed)
    right_change: dict[int, list[str]] = {}

    for tag, i1, i2, j1, j2 in base_to_left.get_opcodes():
        if tag != "equal":
            for bi in range(i1, i2):
                left_change[bi] = left[j1:j2]

    for tag, i1, i2, j1, j2 in base_to_right.get_opcodes():
        if tag != "equal":
            for bi in range(i1, i2):
                right_change[bi] = right[j1:j2]

    # 간단한 라인별 병합
    chunks: list[MergeChunk] = []
    has_conflict = False

    i = 0
    while i < len(base):
        lc = left_change.get(i)
        rc = right_change.get(i)

        if lc is None and rc is None:
            # 변경 없음
            _append_or_merge(chunks, ChunkType.UNCHANGED, [base[i]], [base[i]], [base[i]])
        elif lc is not None and rc is None:
            _append_or_merge(chunks, ChunkType.LEFT_ONLY, [base[i]], lc, [base[i]])
        elif lc is None and rc is not None:
            _append_or_merge(chunks, ChunkType.RIGHT_ONLY, [base[i]], [base[i]], rc)
        elif lc == rc:
            _append_or_merge(chunks, ChunkType.BOTH_SAME, [base[i]], lc, rc)
        else:
            chunk = MergeChunk(
                chunk_type=ChunkType.CONFLICT,
                base_lines=[base[i]],
                left_lines=lc,
                right_lines=rc,
            )
            chunks.append(chunk)
            has_conflict = True
        i += 1

    # base에 없는 insert 처리 (left/right에만 있는 라인)
    # 이미 opcodes에서 처리됐으나 마지막에 추가된 라인 처리
    return chunks, has_conflict


def _append_or_merge(
    chunks: list[MergeChunk],
    chunk_type: ChunkType,
    base: list[str],
    left: list[str],
    right: list[str],
):
    if chunks and chunks[-1].chunk_type == chunk_type:
        chunks[-1].base_lines  += base
        chunks[-1].left_lines  += left
        chunks[-1].right_lines += right
    else:
        chunks.append(MergeChunk(chunk_type, base, left, right))


def chunks_to_text(chunks: list[MergeChunk]) -> str:
    lines = []
    for chunk in chunks:
        lines.extend(chunk.result_lines)
    return "".join(lines)
