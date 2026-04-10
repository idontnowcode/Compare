import difflib
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class LineType(Enum):
    EQUAL = "equal"
    INSERT = "insert"
    DELETE = "delete"
    REPLACE = "replace"
    EMPTY = "empty"


@dataclass
class DiffLine:
    line_no: Optional[int]
    text: str
    line_type: LineType


def compute_diff(left_text: str, right_text: str) -> tuple[list[DiffLine], list[DiffLine]]:
    left_lines = left_text.splitlines(keepends=True)
    right_lines = right_text.splitlines(keepends=True)

    matcher = difflib.SequenceMatcher(None, left_lines, right_lines, autojunk=False)
    opcodes = matcher.get_opcodes()

    left_result: list[DiffLine] = []
    right_result: list[DiffLine] = []

    left_no = 1
    right_no = 1

    for tag, i1, i2, j1, j2 in opcodes:
        left_chunk = left_lines[i1:i2]
        right_chunk = right_lines[j1:j2]

        if tag == "equal":
            for line in left_chunk:
                left_result.append(DiffLine(left_no, line.rstrip("\n"), LineType.EQUAL))
                right_result.append(DiffLine(right_no, line.rstrip("\n"), LineType.EQUAL))
                left_no += 1
                right_no += 1

        elif tag == "replace":
            max_len = max(len(left_chunk), len(right_chunk))
            for i in range(max_len):
                if i < len(left_chunk):
                    left_result.append(DiffLine(left_no, left_chunk[i].rstrip("\n"), LineType.REPLACE))
                    left_no += 1
                else:
                    left_result.append(DiffLine(None, "", LineType.EMPTY))

                if i < len(right_chunk):
                    right_result.append(DiffLine(right_no, right_chunk[i].rstrip("\n"), LineType.REPLACE))
                    right_no += 1
                else:
                    right_result.append(DiffLine(None, "", LineType.EMPTY))

        elif tag == "delete":
            for line in left_chunk:
                left_result.append(DiffLine(left_no, line.rstrip("\n"), LineType.DELETE))
                right_result.append(DiffLine(None, "", LineType.EMPTY))
                left_no += 1

        elif tag == "insert":
            for line in right_chunk:
                left_result.append(DiffLine(None, "", LineType.EMPTY))
                right_result.append(DiffLine(right_no, line.rstrip("\n"), LineType.INSERT))
                right_no += 1

    return left_result, right_result
