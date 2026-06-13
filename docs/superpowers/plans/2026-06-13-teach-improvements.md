# Teach Skill Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the duplicate teach skill files (SKILL.md vs teach.md), rewrite the skill with the new upfront-context workflow and /plans integration, and replace the bot's teach: handler with a proper background thread using the Telegram relay.

**Architecture:** SKILL.md becomes the single canonical skill file (teach.md deleted). The skill reads settings.json at start, accepts topic+context upfront, asks clarifying questions via telegram_ask.py relay, then either batch-creates all lessons immediately or saves a teach plan to scheduled_plans.json. The bot's teach: handler mirrors _run_plan() — fire-and-forget background thread.

**Tech Stack:** Python 3, Claude Code CLI (`claude --dangerously-skip-permissions -p`), Telegram Bot API, PowerShell git commands, HTML lesson files

---

## File Map

| File | Action |
|------|--------|
| `C:\Users\tjark\.claude\skills\teach\SKILL.md` | Rewrite — new workflow, Telegram relay, /plans support |
| `C:\Users\tjark\.claude\skills\teach\teach.md` | Delete |
| `C:\Projekte\telegram-notion-bot\bot.py` | Add `_run_teach()`, replace teach: handler, update HILFE_TEXT |
| `C:\Projekte\telegram-notion-bot\tests\test_bot.py` | Add tests for teach: prefix handling and HILFE_TEXT |

---

### Task 1: Rewrite SKILL.md with new workflow

**Files:**
- Modify: `C:\Users\tjark\.claude\skills\teach\SKILL.md`

- [ ] **Step 1: Read current SKILL.md to confirm it is the original plugin version**

```powershell
Get-Content "C:\Users\tjark\.claude\skills\teach\SKILL.md" -TotalCount 10
```
Expected: frontmatter with `name: teach`, `author: mattpocock`, no "Telegram Relay" section.

- [ ] **Step 2: Overwrite SKILL.md with the merged content**

Write the following complete content to `C:\Users\tjark\.claude\skills\teach\SKILL.md`:

````markdown
---
name: teach
description: Structured teaching workspace. Helps user master a topic through stateful lessons, learning records, missions, and curated resources. Invoke when user wants to learn something or continue a learning session.
argument-hint: "[topic and motivation, or 'continue']"
allowed-tools: Read, Write, Edit, Glob, Bash, WebFetch
user-invocable: true
homepage: https://github.com/mattpocock/skills/tree/main/skills/productivity/teach
author: mattpocock
license: MIT
---

# /teach — Structured Learning Workspace

This skill turns Claude Code into a stateful teaching environment. Each workspace tracks a single learning mission and evolves with the learner.

## Workspace Structure

```
<workspace-root>/
  MISSION.md              ← learner's concrete goal (one screen, one focus)
  NOTES.md                ← scratchpad: preferences, working notes
  RESOURCES.md            ← curated high-trust sources
  GLOSSARY.md             ← mastered terms, compressed definitions
  reference/              ← *.html cheat sheets for quick future lookup
  learning-records/       ← 0001-slug.md, 0002-slug.md … (non-obvious insights)
  lessons/                ← *.html single-concept teaching units
```

## Telegram Relay

At the start of every /teach session, read `C:\Projekte\telegram-notion-bot\settings.json`.

If `notifications_enabled: true`:
- Route ALL questions and decisions through Telegram — never output them as terminal text
- For each question, run via Bash:
  `python "C:\Projekte\telegram-notion-bot\scripts\telegram_ask.py" "your full question with options A) ... B) ..."`
- The Bash stdout is the user's answer — process it and continue

If `notifications_enabled: false`: use normal terminal output.

## On First Invocation

1. Read `C:\Projekte\telegram-notion-bot\settings.json` → `notifications_enabled`
2. Topic + motivation + context come from the user's argument — do NOT ask "what do you want to learn?" as a first question. Parse the argument directly.
3. Determine workspace root: `C:\Projekte\teach\<topic-slug>\` (derive slug from topic)
4. Create workspace directories: `lessons/`, `learning-records/`, `reference/`
5. Ask clarifying questions ONE AT A TIME (via relay if enabled) until shared understanding is confirmed. Good questions: prior knowledge, specific goal, time constraints, scope. Stop when you understand what to teach.
6. Write `MISSION.md` (see format below)
7. Create `RESOURCES.md` stub, `NOTES.md` stub
8. Plan the full lesson sequence: list all concepts to cover (4–8 lessons), ordered by zone of proximal development. Show the list to the user.
9. Ask: `"Lektionen jetzt schreiben oder für später unter /plans speichern?\nA) Jetzt schreiben\nB) Für später speichern"`
10. **If A (Jetzt):** → go to Batch Lesson Creation, then After All Lessons
11. **If B (Später):** → go to Save to Plans

## On Subsequent Invocations (`/teach continue` or `/teach <existing-topic>`)

1. Read `C:\Projekte\telegram-notion-bot\settings.json` → `notifications_enabled`
2. Read existing workspace: `MISSION.md`, `NOTES.md`, `RESOURCES.md`, `GLOSSARY.md`
3. Glob `learning-records/` — read all records to know what has been mastered
4. List existing lessons in `lessons/` — these are already written
5. Ask clarifying questions (via relay if enabled): what depth or extension does the user want? Are there gaps? New direction?
6. Plan new lessons based on the extension, show list to user
7. Batch-create new lessons → After All Lessons

---

## Save to Plans

When the user chooses "B) Später":

**Step 1 — Write the lesson plan markdown:**

Save to `C:\Projekte\telegram-notion-bot\docs\superpowers\plans\YYYY-MM-DD-<slug>-teach.md`:

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
2. <Titel> — <kurze Beschreibung>
...

## Implementation Instructions
Invoke the /teach skill with the topic and context above. Skip clarifying questions — use this plan directly. Create all lessons in batch using the lesson sequence above. Then commit, push, and send Telegram links.
```

**Step 2 — Add to scheduled_plans.json:**

Read `C:\Projekte\telegram-notion-bot\scheduled_plans.json`, append:

```json
{
  "slug": "<slug>-teach",
  "plan_path": "docs/superpowers/plans/YYYY-MM-DD-<slug>-teach.md",
  "scheduled_time": null,
  "status": "pending"
}
```

Write the updated array back.

**Step 3 — Commit:**

```powershell
git -C "C:\Projekte\telegram-notion-bot" add docs/superpowers/plans/YYYY-MM-DD-<slug>-teach.md scheduled_plans.json
git -C "C:\Projekte\telegram-notion-bot" commit -m "chore: save teach plan <slug>"
```

Then notify the user: `"📋 Teach-Plan gespeichert: <slug>-teach\nStarte mit: implement-plan: <slug>-teach jetzt"`

---

## MISSION.md Format

Purpose: documents the learner's concrete goal. All teaching decisions align with it.

```markdown
# Mission

## Why
<Tangible, life-changing outcome. NOT "understand X" — "be able to DO X by DATE">

## Success looks like
<Observable, specific accomplishments the learner will demonstrate>

## Constraints
<Time, resources, preferences, prior knowledge>

## Out of scope
<Adjacent topics deliberately excluded>
```

**Rules:**
- Specificity over abstraction: "Run a half marathon by October" beats "get fitter"
- One mission per workspace — multiple unrelated goals need separate workspaces
- Push back on vagueness: interview the learner if unclear
- Living document: update when circumstances change
- Brevity: fits one screen

---

## Learning Record Format

Location: `./learning-records/NNNN-slug.md` (sequential, lazy-created on first use)

```markdown
# LR-NNNN: <short title>

<1-3 sentences: what was learned and why it matters>

<!-- Optional -->
status: active | superseded by LR-NNNN
evidence: <quote or demonstrated action showing genuine understanding>
```

**When to create:**
- Genuine understanding demonstrated (not mere exposure)
- Prior knowledge disclosed by user
- Misconception identified and corrected
- Mission shift

**What does NOT qualify:** coverage without evidence, glossary-level definitions, activity logs

**Supersession:** mark as superseded instead of deleting — preserves learning evolution

---

## GLOSSARY.md Format

Only add terms after user demonstrates genuine understanding and can apply the concept.

```markdown
# Glossary: <topic>

## <Term>
<1-2 sentences: what it IS, using other glossary terms where possible>

Avoid: <less-precise synonyms>
```

---

## RESOURCES.md Format

```markdown
# Resources

## Knowledge
- [Title](url) - <one-line annotation: scope and when to consult>

## Wisdom (communities)
- [Community](url) - <one-line annotation>

## Gaps
- <Missing resource type: needed but not yet found>
```

**Rules:** primary sources only, recognized experts, peer-reviewed work, well-moderated communities. Remove incorrect/shallow sources entirely.

---

## Lesson Design

Each lesson MUST:
- Teach exactly **one concept**
- Be completable quickly with a tangible outcome
- Connect directly to the mission
- Include citations backing claims
- Include a quiz or interactive task (tight feedback loop)
- End with a summary of what was learned

Lessons saved as `./lessons/<slug>.html` — self-contained, beautifully formatted HTML.

Reference documents (`./reference/<slug>.html`) are compressed cheat sheets for lasting quick-reference, not lesson replacements.

## Batch Lesson Creation

After the lesson plan is shown and confirmed:
- Create every lesson HTML file in sequence
- Do NOT pause for user interaction between lessons
- Do NOT push or notify after individual lessons — wait until ALL are done

## After All Lessons

After ALL lesson HTML files are written, ALWAYS run these two steps.

This fires **always**, regardless of `notifications_enabled` or which project invoked `/teach`.

**Step 1 — Publish all at once:**
```powershell
cd "C:\Projekte\teach"; git add .; git commit -m "Add lessons: <topic-slug>"; git push
```

**Step 2 — Send bundled URLs to Telegram:**
```powershell
$token = $env:TELEGRAM_TOKEN
$baseUrl = "https://djtj9.github.io/teach-lessons/<topic-slug>/lessons"
$lines = @("📚 Neue Lektionen verfügbar:")
# For each lesson slug in creation order:
$lines += "• $baseUrl/<lesson-slug-1>.html"
$lines += "• $baseUrl/<lesson-slug-2>.html"
# ... one line per lesson
$text = $lines -join "`n"
Invoke-WebRequest -Uri "https://api.telegram.org/bot$token/sendMessage" -Method POST -Body @{chat_id="8896609541"; text=$text} -ContentType "application/x-www-form-urlencoded" | Out-Null
```

Replace `<topic-slug>` with the workspace folder name and list every `<lesson-slug>` in order.

---

## Teaching Philosophy

Deep learning requires three elements:

1. **Knowledge** - sourced from high-quality, trustworthy resources
2. **Skills** - acquired through interactive, mission-aligned lessons in zone of proximal development
3. **Wisdom** - gained through real-world practice in communities

Never teach beyond the zone of proximal development. Build on demonstrated knowledge in learning records.
````

- [ ] **Step 3: Verify the file has the new sections**

```powershell
Select-String -Path "C:\Users\tjark\.claude\skills\teach\SKILL.md" -Pattern "notifications_enabled|Telegram Relay|Save to Plans|Batch Lesson"
```
Expected: matches for all four patterns.

---

### Task 2: Delete teach.md

**Files:**
- Delete: `C:\Users\tjark\.claude\skills\teach\teach.md`

- [ ] **Step 1: Confirm SKILL.md has new content before deleting**

```powershell
(Select-String -Path "C:\Users\tjark\.claude\skills\teach\SKILL.md" -Pattern "notifications_enabled").Count
```
Expected: 2 or more.

- [ ] **Step 2: Delete teach.md**

```powershell
Remove-Item "C:\Users\tjark\.claude\skills\teach\teach.md"
```

- [ ] **Step 3: Verify only SKILL.md remains as a .md file in the teach dir root**

```powershell
Get-ChildItem "C:\Users\tjark\.claude\skills\teach\" -Filter "*.md" | Select-Object Name
```
Expected: `SKILL.md` only.

---

### Task 3: Write failing tests for bot teach: changes

**Files:**
- Modify: `C:\Projekte\telegram-notion-bot\tests\test_bot.py`

- [ ] **Step 1: Append the failing tests at the end of tests/test_bot.py**

```python
# --- teach: handler tests ---

def test_teach_prefix_detection():
    text = "teach: Python Grundlagen, weil ich Skripte automatisieren will"
    assert text.lower().startswith("teach:")
    assert text.split(":", 1)[1].strip() == "Python Grundlagen, weil ich Skripte automatisieren will"

def test_teach_slash_prefix_detection():
    text = "/teach Python Grundlagen"
    assert text.lower().startswith("/teach")
    assert text[6:].strip() == "Python Grundlagen"

def test_teach_empty_detection():
    text = "teach:"
    assert text.split(":", 1)[1].strip() == ""

def test_teach_is_known_command():
    known_prefixes = (
        "task:", "status:", "fokus:", "verschieben:", "lern:",
        "idee:", "habit:", "termin:", "projekt:", "teach:", "erinnere", "erinnerung:",
        "implement-plan:", "abort-plan:", "backlog:", "suche:",
    )
    assert "teach: Python".lower().startswith(known_prefixes)

def test_run_teach_exists():
    from bot import _run_teach
    assert callable(_run_teach)

def test_hilfe_contains_teach_with_context():
    from bot import HILFE_TEXT
    assert "teach:" in HILFE_TEXT
    assert "warum" in HILFE_TEXT.lower() or "thema" in HILFE_TEXT.lower()
```

- [ ] **Step 2: Run the two tests that need bot changes to fail**

```bash
cd "C:\Projekte\telegram-notion-bot" && python -m pytest tests/test_bot.py::test_run_teach_exists tests/test_bot.py::test_hilfe_contains_teach_with_context -v 2>&1 | tail -15
```
Expected: `test_run_teach_exists` FAILED with ImportError, `test_hilfe_contains_teach_with_context` FAILED with AssertionError.

- [ ] **Step 3: Run the prefix tests to confirm they already pass**

```bash
cd "C:\Projekte\telegram-notion-bot" && python -m pytest tests/test_bot.py::test_teach_prefix_detection tests/test_bot.py::test_teach_slash_prefix_detection tests/test_bot.py::test_teach_empty_detection tests/test_bot.py::test_teach_is_known_command -v 2>&1 | tail -10
```
Expected: all 4 PASSED (pure string logic, no bot import needed).

---

### Task 4: Add _run_teach() to bot.py

**Files:**
- Modify: `C:\Projekte\telegram-notion-bot\bot.py`

- [ ] **Step 1: Locate _run_plan() to find the insertion point**

```bash
grep -n "def _run_plan\|def _plan_loop" "C:\Projekte\telegram-notion-bot\bot.py"
```
Expected: `_run_plan` at ~line 586, `_plan_loop` at ~line 616.

- [ ] **Step 2: Insert _run_teach() between _run_plan() and _plan_loop()**

Find this line (start of _plan_loop):
```python
def _plan_loop():
```

Insert before it:
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
        timeout=3600, cwd=str(Path(TEACH_DIR).parent), env=env
    )
    if result.returncode != 0:
        send_message(MY_CHAT_ID, f"❌ Teach-Session fehlgeschlagen\n{(result.stderr or '')[-300:]}")

```

- [ ] **Step 3: Run the import test**

```bash
cd "C:\Projekte\telegram-notion-bot" && python -m pytest tests/test_bot.py::test_run_teach_exists -v 2>&1 | tail -10
```
Expected: PASSED.

---

### Task 5: Replace teach: handler and update HILFE_TEXT in bot.py

**Files:**
- Modify: `C:\Projekte\telegram-notion-bot\bot.py`

- [ ] **Step 1: Update the teach: line in HILFE_TEXT**

Find (around line 105):
```python
  teach: <text> — Lernkurs erstellen
```

Replace with:
```python
  teach: <thema + warum> — Lernkurs erstellen oder planen
    z.B. teach: Python Grundlagen, weil ich Skripte automatisieren will
```

- [ ] **Step 2: Replace the teach: handler in the message loop**

Find (around line 1102):
```python
            elif text.lower().startswith("/teach") or text.lower().startswith("teach:"):
                response = run_claude_with_history(chat_id, text, cwd=os.path.dirname(TEACH_DIR))
```

Replace with:
```python
            elif text.lower().startswith("/teach") or text.lower().startswith("teach:"):
                topic = text.split(":", 1)[1].strip() if ":" in text else text[6:].strip()
                if not topic:
                    send_message(chat_id, "Nutzung: teach: <thema + warum>\nz.B. teach: Python Grundlagen, weil ich Skripte automatisieren will", reply_markup=REPLY_KEYBOARD)
                    continue
                send_message(chat_id, "📚 Teach-Session gestartet — Fragen kommen gleich über den Chat")
                threading.Thread(target=_run_teach, args=(topic,), daemon=True).start()
                continue
```

- [ ] **Step 3: Run all teach: tests**

```bash
cd "C:\Projekte\telegram-notion-bot" && python -m pytest tests/test_bot.py::test_hilfe_contains_teach_with_context tests/test_bot.py::test_run_teach_exists tests/test_bot.py::test_teach_prefix_detection tests/test_bot.py::test_teach_slash_prefix_detection tests/test_bot.py::test_teach_empty_detection -v 2>&1 | tail -15
```
Expected: all 5 PASSED.

---

### Task 6: Run full test suite and commit

**Files:**
- `C:\Projekte\telegram-notion-bot\bot.py`
- `C:\Projekte\telegram-notion-bot\tests\test_bot.py`

- [ ] **Step 1: Run all tests**

```bash
cd "C:\Projekte\telegram-notion-bot" && python -m pytest tests/ -v 2>&1 | tail -30
```
Expected: all tests PASSED, no failures.

- [ ] **Step 2: Commit bot.py and test changes**

```bash
git -C "C:\Projekte\telegram-notion-bot" add bot.py tests/test_bot.py
git -C "C:\Projekte\telegram-notion-bot" commit -m "feat: replace teach: handler with background thread + _run_teach()"
```
