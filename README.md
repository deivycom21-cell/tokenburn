# TokenBurn

Measure wasted tokens in Claude Code sessions: **how much did you spend on work that never made it into the final diff?**

> **Not affiliated with, endorsed by, or sponsored by Anthropic.**
> Claude® is a trademark of Anthropic.
> Cost shown is the API rate. If you use Claude Pro or Max, your actual cost is covered by your subscription.

---

## Install

```bash
pipx install tokenburn
```

## Usage

```bash
# Analyze the most recent session
tokenburn analyze

# Analyze a specific session file
tokenburn analyze ~/.claude/projects/<hash>/<session>.jsonl

# JSON output
tokenburn analyze --json

# Share mode: hide paths and project name before screenshotting
tokenburn analyze --share

# Suppress the footer line
tokenburn analyze --no-funnel
# or: export TOKENBURN_NO_FUNNEL=1

# List available sessions
tokenburn list
```

## Example output

```
TokenBurn Report
================================================
Session: ~/.claude/projects/abc123/sess.jsonl
Model:   claude-sonnet-4-6

Tokens
------------------------
  Input:              300
  Output:             150
  Cache read:           0
  Cache write:          0
  Total:              450

API-equivalent cost: $0.0013
⚠  This is the API rate. If you use Claude Pro/Max, your actual
   cost per session is covered by your subscription.

Burn  (writes not in final diff)
------------------------------------------------
  Burned turns:  1 / 3 write turns (33.3%)
  Burned tokens: 150 / 450 total (33.3%)

Files touched
------------------------------------------------
  /project/hello.py                        +5 -0
  /project/utils.py                        +2 -0  [not mentioned]

------------------------------------------------
Measure your burn → tokenburn.sh
```

---

## Burn rule (criterion 4)

**Only writes whose result does not survive in the final diff are counted.**

Decision: Deivy, 6 Nov. This rule is intentionally simple and is not changed by TokenBurn.

A *write* is:
| Tool | Counts as write? |
|------|-----------------|
| `Write` (create/overwrite file) | ✅ Yes |
| `Edit` / `MultiEdit` (modify file) | ✅ Yes |
| `Bash` with redirect (`>`, `>>`, `tee`) | ✅ Yes |
| `Bash` with `rm`, `mv`, `cp`, `mkdir`, `touch` | ✅ Yes |
| `Bash` with `git add/commit/push` | ✅ Yes |
| `Bash` running checks (pytest, eslint, mypy, …) | ❌ No |
| `Read`, `Glob`, `Grep` | ❌ No |

**Within a session**, a write to file `F` in turn `T` is *burned* when a later turn also writes `F` (overwriting the work). A turn is counted as burned if it has file writes **and every one of those file writes is subsequently overwritten**.

> Note: This measures within-session overwrite burn. Git diff comparison (cross-session) is planned for v1.

Reasoning tokens before a failure are **not** counted in v0 (see Ficha 003 — out of scope, revisit in v1).

---

## Scope / "not mentioned" heuristic (criterion 5)

TokenBurn lists all files the agent touched and marks files whose **name or path does not appear in any user message** as `[not mentioned]`.

This is a declared heuristic — no LLM is used. The label is "not mentioned", not "unrelated", because the absence of a filename in the transcript does not prove the work was unwanted; it is a signal for the user to review.

---

## What is not in scope (v0)

- Reasoning-token burn (R1 · Gemini) — revisit in v1
- Cursor or other agents
- LLM-assisted analysis
- Web dashboard, user accounts, cloud sync
- Crow-specific features
