import os, subprocess
from pathlib import Path

WORK_DIR = os.environ.get("WORK_DIR", "/root/projekte/telegram-bot-army")

def run_claude(prompt, system_prompt=None, cwd=None, automated=False, allowed_tools=None):
    tools = allowed_tools or "Bash,Read,Write,Edit,Glob,Grep"
    cmd = ["claude", "--allowedTools", tools]
    if system_prompt:
        cmd += ["--system-prompt", system_prompt]
    cmd += ["-p", prompt]
    env = {**os.environ, "CLAUDE_AUTOMATED": "1"} if automated else None
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8",
            timeout=3600, cwd=cwd or WORK_DIR, env=env,
        )
        return (result.stdout or "").strip() or (result.stderr or "").strip() or "(keine Antwort)"
    except subprocess.TimeoutExpired:
        return "⏱ Timeout — Aufgabe hat länger als 20 Minuten gedauert."

def run_claude_with_history(chat_id, text, history, system_prompt=None, cwd=None):
    """Returns (response_str, updated_history_dict)."""
    msgs = history.get(chat_id, [])
    if msgs and not system_prompt:
        context = "\n".join(
            f"[{'USER' if m['role'] == 'user' else 'ASSISTANT'}]: {m['content']}"
            for m in msgs
        )
        prompt = f"Vorheriger Gesprächsverlauf:\n{context}\n\n[USER]: {text}"
    else:
        prompt = text
    response = run_claude(prompt, system_prompt=system_prompt, cwd=cwd)
    if not system_prompt:
        msgs = msgs + [
            {"role": "user", "content": text},
            {"role": "assistant", "content": response},
        ]
        history = {**history, chat_id: msgs[-6:]}
    return response, history

def run_claude_parse(prompt, system_prompt, work_dir=None):
    _dir = work_dir or WORK_DIR
    cfg = Path(_dir) / ".parse_mcp_empty.json"
    cfg.write_text('{"mcpServers": {}}', encoding="utf-8")
    try:
        cmd = [
            "claude", "--permission-mode", "plan",
            "--strict-mcp-config", "--mcp-config", str(cfg),
            "--system-prompt", system_prompt, "-p", prompt,
        ]
        env = {**os.environ, "CLAUDE_AUTOMATED": "1"}
        result = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8",
            timeout=30, cwd=_dir, env=env,
        )
        return (result.stdout or "").strip() or "{}"
    except subprocess.TimeoutExpired:
        return "{}"
    finally:
        cfg.unlink(missing_ok=True)
