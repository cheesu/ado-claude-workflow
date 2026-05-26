---
name: ado-session-review
description: Generate a session review report for a completed ADO task. Analyzes per-agent token usage, tool call efficiency, waste points, and improvement suggestions. Use when the user wants to review how a session went.
user-invocable: true
---

# ADO Session Review

Generate a structured review report for a completed task session.

## Inputs

The user may specify:
- **Task number** (required) — e.g. `70123`
- **Session ID** (optional) — if omitted, auto-detect the latest session
- **Depth** (optional):
  - `summary` — agent totals + top waste points only
  - `full` (default) — turn-by-turn breakdown per agent phase

If the user did not specify, infer the task number from the current branch:
```bash
git branch --show-current
```

## Step 1 — Collect raw session data

Run `ado_session_log.py` to extract token and tool call data from Claude Code's JSONL history:

```bash
# Auto-detect latest session
python3 "{{FRONTEND_ROOT}}/.claude/hooks/scripts/ado_session_log.py" analyze \
  --task-number <taskNumber> \
  --auto-session \
  --project-dir "{{FRONTEND_ROOT}}"
```

If the user provided a session ID:
```bash
python3 "{{FRONTEND_ROOT}}/.claude/hooks/scripts/ado_session_log.py" analyze \
  --task-number <taskNumber> \
  --session-id <sessionId> \
  --project-dir "{{FRONTEND_ROOT}}"
```

Capture the output — this is the raw per-agent breakdown (tool counts, token usage by phase).

If the script cannot find a session, report the error and stop.

## Step 2 — Read supporting context

Read any existing task log for additional context:
```bash
ls "{{FRONTEND_ROOT}}/.claude/logs/tasks/" | grep <taskNumber>
```

If a log file exists, read it for task description, branch, and outcome fields.

## Step 3 — Analyze and write the report

Using the raw data from Step 1 and context from Step 2, produce a report with the following sections.

**Always write in the same language the user is using.**

---

### Report structure

#### Header
- Task number, title (from log if available), branch, session ID, analysis date

#### 1. Overall summary table
Per-agent: model, API call count, token breakdown (input / output / cache_read / cache_create), share of total cost.
Add a one-line interpretation: which agent dominated cost and whether that was expected.

#### 2. Phase breakdown per agent

For each agent (planner, implementer, reviewer), break the session into phases:
- **Planner**: Explore → Core analysis → Implementation planning
- **Implementer**: Explore → Implement → Verify
- **Reviewer**: Inspect diff → Deep checks → Verdict

For each phase, list:
- What tools were called and what they did (from raw data)
- Token cost for the phase
- Any anomalies (repeated calls, redundant reads, wide searches)

Skip phases with zero activity.

**Depth = `summary`**: Skip the turn-by-turn detail, show only phase subtotals.

#### 3. Waste points

Identify concrete inefficiencies — only real ones observed in the data, not generic advice.

For each waste point:
- What happened (turns/calls involved)
- Why it was wasteful
- What should have been done instead

#### 4. Tool usage analysis

For the planner, categorize Grep/Bash calls:
- Justified (JSON files, JSX prop values, string patterns)
- Should have used symbol search instead
- Redundant (same pattern searched twice)

#### 5. Improvement suggestions

Concrete rules to add to the planner prompt or handoff, derived from the waste points found.
Only include suggestions that this specific session actually warrants.

#### 6. Efficiency scores

| Agent | Score | Rationale |
|---|---|---|
| Planner explore efficiency | X/10 | ... |
| Implementer efficiency | X/10 | ... |
| Reviewer quality | X/10 | ... |
| **Overall** | **X/10** | ... |

---

## Step 4 — Save the report

Save the report as Markdown:

```bash
# Determine output path
REPORT_PATH="{{FRONTEND_ROOT}}/.claude/docs/<taskNumber>_SESSION_REVIEW_REPORT.md"
```

Write the report to that path. Then tell the user:
- The report path
- Overall score
- Top 1–2 waste points in one sentence each

## Step 5 — HTML export (optional)

Only if the user explicitly asked for HTML output.

Convert the Markdown report to a self-contained HTML file with dark-theme styling.
Save as `<taskNumber>_SESSION_REVIEW_REPORT.html` in the same directory.

Use this CSS variable palette:
```css
--planner: #6366f1; --impl: #10b981; --reviewer: #f59e0b;
--bg: #0f172a; --surface: #1e293b; --surface2: #273344;
--border: #334155; --text: #e2e8f0; --muted: #94a3b8;
```
