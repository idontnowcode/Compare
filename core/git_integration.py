"""Git 연동: git diff, git show, 브랜치/커밋 목록."""
import subprocess
import os
from dataclasses import dataclass


@dataclass
class GitCommit:
    sha: str
    short_sha: str
    message: str
    author: str
    date: str


def _run(args: list[str], cwd: str = ".") -> str:
    try:
        result = subprocess.run(
            args, cwd=cwd,
            capture_output=True, text=True, timeout=15
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip())
        return result.stdout
    except FileNotFoundError:
        raise RuntimeError("git 명령어를 찾을 수 없습니다. Git이 설치되어 있는지 확인하세요.")
    except subprocess.TimeoutExpired:
        raise RuntimeError("git 명령 시간 초과")


def is_git_repo(path: str) -> bool:
    try:
        _run(["git", "rev-parse", "--is-inside-work-tree"], cwd=path)
        return True
    except Exception:
        return False


def get_repo_root(path: str) -> str:
    return _run(["git", "rev-parse", "--show-toplevel"], cwd=path).strip()


def list_branches(repo_path: str) -> list[str]:
    out = _run(["git", "branch", "--all", "--format=%(refname:short)"], cwd=repo_path)
    return [b.strip() for b in out.splitlines() if b.strip()]


def list_commits(repo_path: str, branch: str = "HEAD", n: int = 100) -> list[GitCommit]:
    fmt = "%H|%h|%s|%an|%ad"
    out = _run(
        ["git", "log", branch, f"-{n}", f"--format={fmt}", "--date=short"],
        cwd=repo_path
    )
    commits = []
    for line in out.splitlines():
        parts = line.split("|", 4)
        if len(parts) == 5:
            commits.append(GitCommit(*parts))
    return commits


def get_file_at_commit(repo_path: str, commit: str, rel_path: str) -> str:
    """특정 커밋의 파일 내용 반환."""
    return _run(["git", "show", f"{commit}:{rel_path}"], cwd=repo_path)


def get_diff_text(repo_path: str, commit1: str, commit2: str, rel_path: str = "") -> str:
    """두 커밋 간 diff 텍스트 반환."""
    args = ["git", "diff", commit1, commit2]
    if rel_path:
        args += ["--", rel_path]
    return _run(args, cwd=repo_path)


def get_working_diff(repo_path: str, rel_path: str = "") -> tuple[str, str]:
    """
    워킹 트리의 현재 파일과 HEAD 버전을 반환.
    Returns (head_content, working_content).
    """
    working_path = os.path.join(repo_path, rel_path) if rel_path else repo_path
    try:
        head_content = _run(["git", "show", f"HEAD:{rel_path}"], cwd=repo_path)
    except Exception:
        head_content = ""
    try:
        with open(working_path, encoding="utf-8", errors="replace") as f:
            working_content = f.read()
    except OSError:
        working_content = ""
    return head_content, working_content


def list_changed_files(repo_path: str, commit1: str = "HEAD~1", commit2: str = "HEAD") -> list[str]:
    """두 커밋 간 변경된 파일 목록."""
    out = _run(["git", "diff", "--name-only", commit1, commit2], cwd=repo_path)
    return [f.strip() for f in out.splitlines() if f.strip()]
