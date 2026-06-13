# Teach Skill Improvements — Design

## Problem

Two issues in the current teach setup:

1. **Duplicate skill files:** `SKILL.md` (original plugin, CC reads this) and `teach.md` (customized) coexist. CC uses `SKILL.md`, which lacks batch creation, Telegram publishing, and the correct workspace path. Customizations in `teach.md` are silently ignored.
2. **Workflow friction:** First invocation asks an open question instead of accepting upfront context. No "save to /plans" option. Bot's `teach:` handler uses `run_claude_with_history` (no skill invoked, no lessons ever written from bot).

## Fix: Duplicate

Merge `teach.md` content into `SKILL.md`. Delete `teach.md`. One canonical file.

## New Teach Skill Workflow (`SKILL.md`)

### On First Invocation

1. Read `C:\Projekte\telegram-notion-bot\settings.json` → `notifications_enabled`
2. Accept topic + motivation + context from initial user argument — no separate intro question
3. Determine workspace root: `C:\Projekte\teach\<topic-slug>\`, create directories
4. Ask clarifying questions one at a time (via `telegram_ask.py` if `notifications_enabled: true`, else terminal) until shared understanding is confirmed
5. Write `MISSION.md`
6. Plan full lesson sequence (4–8 lessons), show list to user
7. Ask: `"Lektionen jetzt schreiben oder für später unter /plans speichern? A) Jetzt  B) Später"`
8. **A — Jetzt:** batch-create all lesson HTML files → commit+push → send Telegram links
9. **B — Später:** write lesson plan markdown → add to `scheduled_plans.json` → git commit

### On Subsequent Invocations (`/teach continue` or `/teach <existing-topic>`)

1. Read existing workspace: `MISSION.md`, learning records, existing lessons
2. Ask clarifying questions about desired depth or extension (relay if enabled)
3. Plan new lessons, show list
4. Batch-create → commit+push → Telegram links

### Telegram Relay (questions)

Same pattern as brainstorming:
```bash
python "C:\Projekte\telegram-notion-bot\scripts\telegram_ask.py" "question text with options"
```
Stdout = user's answer. Apply only when `notifications_enabled: true`.

### Batch Lesson Creation (unchanged)

After lesson plan is confirmed:
- Create every lesson HTML in sequence
- No pause between lessons
- No push/notify until ALL are done

### After All Lessons (unchanged)

```powershell
cd "C:\Projekte\teach"; git add .; git commit -m "Add lessons: <topic-slug>"; git push
```
Then send bundled Telegram URLs.

## "Save to /plans" Format

### Plan markdown: `docs/superpowers/plans/YYYY-MM-DD-<slug>-teach.md`

```markdown
# Teach Plan: <Thema>

## Topic
<Thema>

## Why
<Motivation>

## Workspace
C:\Projekte\teach\<slug>\

## Lesson Sequence
1. <Titel> — <kurze Beschreibung>
2. ...

## Implementation Instructions
Run /teach skill with this context. Skip clarifying questions — use this plan directly. Create all lessons in batch.
```

### `scheduled_plans.json` entry

```json
{
  "slug": "<slug>-teach",
  "plan_path": "docs/superpowers/plans/YYYY-MM-DD-<slug>-teach.md",
  "scheduled_time": null,
  "status": "pending"
}
```

When `implement-plan: <slug>-teach jetzt` runs, `_run_plan` reads this file and CC writes all lessons without asking questions.

## Bot Changes (`bot.py`)

### `teach:` handler

Replace `run_claude_with_history` with a background thread (same pattern as `_run_plan`):

```python
elif text.lower().startswith("/teach") or text.lower().startswith("teach:"):
    topic = text.split(":", 1)[1].strip() if ":" in text else text[6:].strip()
    if not topic:
        response = "Nutzung: teach: <thema + warum>  z.B. teach: Python Grundlagen, weil ich Skripte automatisieren will"
        send_message(chat_id, response, reply_markup=REPLY_KEYBOARD)
        continue
    send_message(chat_id, "📚 Teach-Session gestartet — Fragen kommen gleich über den Chat")
    threading.Thread(
        target=_run_teach,
        args=(topic,),
        daemon=True
    ).start()
    continue
```

New `_run_teach(topic)` function:
```python
def _run_teach(topic):
    prompt = (
        f"Invoke the /teach skill. "
        f"Topic and context from user: {topic}. "
        f"Use telegram relay for questions if notifications_enabled."
    )
    cmd = ["claude", "--dangerously-skip-permissions", "-p", prompt]
    env = {**os.environ, "CLAUDE_AUTOMATED": "1"}
    result = subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8",
        timeout=3600, cwd=str(Path(TEACH_DIR).parent)
    )
    if result.returncode != 0:
        send_message(MY_CHAT_ID, f"❌ Teach-Session fehlgeschlagen\n{(result.stderr or '')[-300:]}")
```

### `HILFE_TEXT`

```
teach: <thema + warum> — Lernkurs erstellen oder planen
  z.B. teach: Python Grundlagen, weil ich Skripte automatisieren will
```

### `/plans` integration

No bot changes needed. Teach plans appear in `_format_plans()` automatically via `scheduled_plans.json`.

## Files Changed

| File | Change |
|------|--------|
| `C:\Users\tjark\.claude\skills\teach\SKILL.md` | Merge teach.md content + new workflow |
| `C:\Users\tjark\.claude\skills\teach\teach.md` | Delete |
| `C:\Projekte\telegram-notion-bot\bot.py` | Replace teach: handler, add `_run_teach()`, update HILFE_TEXT |
