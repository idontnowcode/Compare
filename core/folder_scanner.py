import os
import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class FileStatus(Enum):
    IDENTICAL = "identical"
    DIFFERENT = "different"
    LEFT_ONLY = "left_only"
    RIGHT_ONLY = "right_only"


@dataclass
class FileEntry:
    name: str
    rel_path: str
    status: FileStatus
    is_dir: bool
    children: list["FileEntry"] = field(default_factory=list)


def _file_hash(path: str) -> str:
    h = hashlib.md5()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
    except OSError:
        return ""
    return h.hexdigest()


def scan_folders(left_root: str, right_root: str, rel: str = "") -> list[FileEntry]:
    left_dir = os.path.join(left_root, rel)
    right_dir = os.path.join(right_root, rel)

    left_names: set[str] = set()
    right_names: set[str] = set()

    if os.path.isdir(left_dir):
        left_names = set(os.listdir(left_dir))
    if os.path.isdir(right_dir):
        right_names = set(os.listdir(right_dir))

    all_names = sorted(left_names | right_names, key=lambda n: (not os.path.isdir(os.path.join(left_dir, n) if n in left_names else os.path.join(right_dir, n)), n.lower()))

    entries: list[FileEntry] = []

    for name in all_names:
        rel_path = os.path.join(rel, name) if rel else name
        left_path = os.path.join(left_root, rel_path)
        right_path = os.path.join(right_root, rel_path)

        left_exists = name in left_names
        right_exists = name in right_names

        left_is_dir = left_exists and os.path.isdir(left_path)
        right_is_dir = right_exists and os.path.isdir(right_path)
        is_dir = left_is_dir or right_is_dir

        if not left_exists:
            status = FileStatus.RIGHT_ONLY
        elif not right_exists:
            status = FileStatus.LEFT_ONLY
        elif is_dir:
            status = FileStatus.IDENTICAL
        else:
            lh = _file_hash(left_path)
            rh = _file_hash(right_path)
            status = FileStatus.IDENTICAL if lh == rh else FileStatus.DIFFERENT

        entry = FileEntry(name=name, rel_path=rel_path, status=status, is_dir=is_dir)

        if is_dir and (left_is_dir or right_is_dir):
            children = scan_folders(left_root, right_root, rel_path)
            entry.children = children
            if any(c.status != FileStatus.IDENTICAL for c in _flatten(children)):
                entry.status = FileStatus.DIFFERENT

        entries.append(entry)

    return entries


def _flatten(entries: list[FileEntry]) -> list[FileEntry]:
    result = []
    for e in entries:
        result.append(e)
        result.extend(_flatten(e.children))
    return result
