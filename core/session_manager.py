import os, json, signal, re, uuid
from datetime import datetime
from pathlib import Path

WORK_DIR = Path(os.environ.get("WORK_DIR", "/root/projekte/telegram-bot-army"))

_STATE_PATH = WORK_DIR / "session_state.json"
_COMMENT_PATH = WORK_DIR / "pending_comment.json"


def save_session(type: str, slug: str, pid: int, checkpoint_path: str | None = None) -> None:
    session_id = str(uuid.uuid4())[:8]
    cp = checkpoint_path or str(Path("/tmp") / f"checkpoint_{session_id}.md")
    _STATE_PATH.write_text(json.dumps({
        "active": type,
        "slug": slug,
        "session_id": session_id,
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "pid": pid,
        "checkpoint_path": cp,
    }, ensure_ascii=False))


def load_session() -> dict | None:
    if not _STATE_PATH.exists():
        return None
    try:
        return json.loads(_STATE_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def clear_session() -> None:
    _STATE_PATH.unlink(missing_ok=True)


def is_session_active() -> bool:
    return load_session() is not None


def kill_session() -> bool:
    s = load_session()
    if not s:
        return False
    try:
        os.kill(s["pid"], signal.SIGTERM)
        return True
    except (ProcessLookupError, OSError):
        return False


def write_comment(text: str) -> None:
    _COMMENT_PATH.write_text(json.dumps({"comment": text}, ensure_ascii=False))


def read_and_clear_comment() -> str | None:
    if not _COMMENT_PATH.exists():
        return None
    try:
        data = json.loads(_COMMENT_PATH.read_text())
        _COMMENT_PATH.unlink(missing_ok=True)
        return data.get("comment")
    except (json.JSONDecodeError, OSError):
        return None


def checkpoint_path(session_id: str) -> Path:
    return Path("/tmp") / f"checkpoint_{session_id}.md"


def write_checkpoint(session_id: str, content: str) -> None:
    checkpoint_path(session_id).write_text(content, encoding="utf-8")


def load_checkpoint(session_id: str) -> str | None:
    p = checkpoint_path(session_id)
    if not p.exists():
        return None
    return p.read_text(encoding="utf-8")


def parse_plan_tasks(plan_path: Path) -> list[dict]:
    content = plan_path.read_text(encoding="utf-8")
    blocks = re.split(r"^## Task \d+:\s*", content, flags=re.MULTILINE)
    tasks = []
    for block in blocks[1:]:
        lines = block.strip().splitlines()
        if not lines:
            continue
        title_line = lines[0].strip()
        done = title_line.startswith("~~") and title_line.endswith("~~")
        title = title_line.strip("~").strip()
        files_match = re.search(r"\*\*Dateien:\*\*\s*(.+)", block)
        files = files_match.group(1).strip() if files_match else ""
        tasks.append({"title": title, "description": block, "files": files, "done": done})
    return tasks


def mark_task_done(plan_path: Path, task_title: str) -> None:
    content = plan_path.read_text(encoding="utf-8")
    updated = re.sub(
        rf"(^## Task \d+:\s*){re.escape(task_title)}",
        rf"\1~~{task_title}~~",
        content,
        count=1,
        flags=re.MULTILINE,
    )
    plan_path.write_text(updated, encoding="utf-8")


def next_pending_task(plan_path: Path) -> dict | None:
    for task in parse_plan_tasks(plan_path):
        if not task["done"]:
            return task
    return None
