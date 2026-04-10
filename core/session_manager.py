"""세션 저장/불러오기 (JSON)."""
import json
import os
from dataclasses import dataclass, field, asdict
from typing import Any


SESSION_DIR = os.path.join(os.path.expanduser("~"), ".compare_app")
SESSION_FILE = os.path.join(SESSION_DIR, "session.json")
RECENT_FILE  = os.path.join(SESSION_DIR, "recent.json")

MAX_RECENT = 20


@dataclass
class TabSession:
    tab_type:   str   # "text" | "folder" | "merge" | "image" | "binary"
    left_path:  str = ""
    right_path: str = ""
    base_path:  str = ""   # merge용
    label:      str = ""


@dataclass
class AppSession:
    tabs: list[TabSession] = field(default_factory=list)
    current_tab: int = 0
    window_geometry: dict = field(default_factory=dict)


def _ensure_dir():
    os.makedirs(SESSION_DIR, exist_ok=True)


# ── 세션 저장/불러오기 ─────────────────────────────────────


def save_session(session: AppSession):
    _ensure_dir()
    data = {
        "version": 1,
        "current_tab": session.current_tab,
        "window_geometry": session.window_geometry,
        "tabs": [asdict(t) for t in session.tabs],
    }
    with open(SESSION_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_session() -> AppSession | None:
    if not os.path.exists(SESSION_FILE):
        return None
    try:
        with open(SESSION_FILE, encoding="utf-8") as f:
            data = json.load(f)
        tabs = [TabSession(**t) for t in data.get("tabs", [])]
        return AppSession(
            tabs=tabs,
            current_tab=data.get("current_tab", 0),
            window_geometry=data.get("window_geometry", {}),
        )
    except Exception:
        return None


def clear_session():
    if os.path.exists(SESSION_FILE):
        os.remove(SESSION_FILE)


# ── 최근 파일 목록 ────────────────────────────────────────


def load_recent() -> list[dict]:
    if not os.path.exists(RECENT_FILE):
        return []
    try:
        with open(RECENT_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def add_recent(tab_type: str, left_path: str, right_path: str):
    _ensure_dir()
    recent = load_recent()
    entry = {"type": tab_type, "left": left_path, "right": right_path}
    # 중복 제거
    recent = [r for r in recent if not (r.get("left") == left_path and r.get("right") == right_path)]
    recent.insert(0, entry)
    recent = recent[:MAX_RECENT]
    with open(RECENT_FILE, "w", encoding="utf-8") as f:
        json.dump(recent, f, ensure_ascii=False, indent=2)


def clear_recent():
    if os.path.exists(RECENT_FILE):
        os.remove(RECENT_FILE)
