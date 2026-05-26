---
name: ado-pickup-task
description: Pick up an Azure DevOps task for frontend work. Use when the user wants to see assigned work items, move one to In Progress, create a work branch from {{BASE_BRANCH}}, and prepare an implementation handoff.
user-invocable: true
---

# ADO Pickup Task

Use this workflow when starting a {{PRODUCT_CODE}} frontend task in `{{FRONTEND_ROOT}}`.

Always load the `ado-guardrails` skill first.

## Goal

Turn an assigned Azure DevOps work item into a safe local work session:

1. Find the user's assigned work items.
2. Let the user choose one.
3. Move it to `In Progress` or the matching active state.
4. Ensure the repo is based on `{{BASE_BRANCH}}`.
5. Create `{{BRANCH_PREFIX}}/{type}/{taskNumber}`.
6. Produce a strong implementation handoff with the `planner-opus-4_6` subagent.

## Mandatory user approval gates

Never start work implicitly.

- If there are multiple candidate work items, show the list first and let the user choose one.
- If there is exactly one candidate work item, still ask whether to start it now.
- After the work item is chosen, ask for explicit confirmation before either of these actions:
  - moving the work item to `In Progress`
  - creating `{{BRANCH_PREFIX}}/{type}/{taskNumber}`

Do not perform either action until the user clearly approves.

## Tool priority

1. Azure DevOps MCP if available and authenticated
2. Azure CLI with `azure-devops` extension
3. Manual fallback with commands and URLs for the user

For this workflow, use:

- organization: `https://dev.azure.com/{{ADO_ORG}}`
- project: `{{ADO_PROJECT}}`

## Startup checks

Before touching Azure DevOps or git:

1. Confirm the current branch state with:
   - `git branch --show-current`
   - `git status --short`
2. If the working tree has unrelated changes, stop and ask the user how to proceed.
3. This workflow must create or reuse work branches only from the `{{BASE_BRANCH}}` line.
4. Before creating a new work branch, separately run and verify:
   - `git checkout {{BASE_BRANCH}}`
   - `git pull --ff-only origin {{BASE_BRANCH}}`
   - `git rev-parse HEAD`
   - `git rev-parse origin/{{BASE_BRANCH}}`
5. If `HEAD` does not exactly match `origin/{{BASE_BRANCH}}`, stop and fix that first.
6. Do not create the work branch inside the same compound shell command that fetches or checks out `{{BASE_BRANCH}}`. Create it only after the base branch has been verified in a separate command.

## Azure DevOps selection flow

### With MCP

- Query assigned work items for the current user in project `{{ADO_PROJECT}}`.
- When using MCP tools, pass the project explicitly as `{{ADO_PROJECT}}` instead of relying on inferred defaults.
- Show a compact list with:
  - work item id
  - type
  - title
  - current state

### With Azure CLI

```bash
az devops configure --list
```

Use `https://dev.azure.com/{{ADO_ORG}}` and `{{ADO_PROJECT}}` as the default org/project.

Then use a WIQL query:

```text
SELECT
  [System.Id],
  [System.WorkItemType],
  [System.Title],
  [System.State]
FROM WorkItems
WHERE
  [System.AssignedTo] = @Me
  AND [System.State] <> 'Done'
  AND [System.State] <> 'Closed'
ORDER BY [Microsoft.VSTS.Common.Priority] ASC, [System.ChangedDate] DESC
```

## Branch creation rules

Classify the chosen work item before creating the branch:

- bug fix → `fix`
- feature or user story with new functionality → `feature`
- refactor-only cleanup → `refactor`
- dependency or resource update → `update`
- tests only → `test`
- docs only → `docs`
- config/tooling → `chore`

Before changing work item state or creating the branch, write the start approval token:

```bash
python3 "{{FRONTEND_ROOT}}/.claude/hooks/scripts/ado_start_approval.py" approve \
  --repo {{REPO_ROOT}} \
  --branch-type <type> \
  --work-item <taskNumber>
```

If the user declines, stop immediately and do not change Azure DevOps or git state.

Branch name:

```text
{{BRANCH_PREFIX}}/{type}/{taskNumber}
```

## Required git sequence

From repo root:

```bash
git checkout {{BASE_BRANCH}}
git pull --ff-only origin {{BASE_BRANCH}}
git rev-parse HEAD
git rev-parse origin/{{BASE_BRANCH}}
git checkout -b {{BRANCH_PREFIX}}/{type}/{taskNumber}
```

Run the branch creation as its own git command after the base verification above.

If the branch already exists locally or remotely, verify its ancestry first:

```bash
git merge-base "{{BRANCH_PREFIX}}/{type}/{taskNumber}" origin/{{BASE_BRANCH}}
git merge-base origin/main origin/{{BASE_BRANCH}}
```

## Work item state update

Only after explicit start approval:

- Move it to the active working state (`In Progress` preferred).
- If the project uses a different active state, use the closest non-done working state and report it.

## Task complexity classification

### Step 1: Description signal check (no tools)

Read the ADO description and look for signals — no tool calls yet.

**Clear light signals** (ALL must apply):
- Explicitly about visual/style only: prop removal, color, size, text change, icon swap
- No mention of logic, behavior, state, API, or data flow
- Specific UI element named (not vague)

**Immediate standard signals** (ANY → skip to standard, no Grep needed):
- "logic", "behavior", "feature" mentioned
- State management or API involved
- New feature or new component
- Vague description without specific element

### Step 2: One Grep confirmation (light candidates only)

Only if Step 1 gives clear light signals, run **exactly one** Grep to confirm:

```bash
grep -r "{keyword}" {{WORK_PATH}}/ --include="*.tsx" --include="*.ts" -l
```

- Result confirms style-only (prop, className, text) → **light**
- Result shows state/hook/logic → **standard**
- Result is ambiguous or requires more investigation → **standard immediately**

> **Hard rule: max 1 Grep call in pre-classification.**
> If 1 Grep is not enough to confirm light, stop and classify as standard.

### Light mode

For light tasks, skip the full planner-implementer-reviewer pipeline:

1. Produce a brief inline plan (max 10 lines) directly in the conversation — no planner spawn.
2. Ask the user: "Simple change detected. Proceed with implementation?"
3. If confirmed, spawn `implementer-sonnet`.
   - Write a minimal handoff to `.claude/state/handoff.md` with exact file paths and changes before spawning.
4. Run verification: `yarn eslint {changed files}` + `yarn tsc --noEmit`.
5. Proceed to user confirmation → commit → PR with the same approval gates as standard mode.

### Light → Standard escalation

If during light mode implementation the implementer encounters unexpected complexity:
1. Stop immediately — do NOT continue implementing.
2. Report to user: "More complex changes needed than expected. [reason]. Run planner?"
3. If user confirms, spawn `planner-opus-4_6` with the orchestrator's existing findings.
4. Continue as standard mode from the planner step.

Signals to escalate:
- More than 5 files need changes
- TypeScript errors requiring interface changes
- State management modification needed
- Chain reaction discovered ("changing X also requires Y")

### Standard mode

For standard tasks, use the full pipeline below.

## Planner handoff

After the branch exists, spawn `planner-opus-4_6`.

### Planner two-phase protocol

Tell the planner to follow this exact two-phase approach:

**Phase 1 — Quick complexity scan (max 5 Serena calls):**

- Step 0: Call `mcp__serena__initial_instructions` first
- Use at most 5 Serena tool calls to locate the target area
- Goal: determine if the change is purely visual/style with no logic involvement
- Write verdict at the very top of the handoff:

```markdown
## Verdict
light|standard
```

**Phase 2 — Handoff based on verdict:**

If verdict is `light`:

```markdown
## Verdict
light

## Target
- file: {exact file path}
- location: line {N} — {exact old code}
- change: {exact new code or "remove this line"}
(repeat for each change — max 5 entries)

## Verification
- yarn eslint {file}
- yarn tsc --noEmit
```

If verdict is `standard`:

```markdown
## Verdict
standard

## Work Summary
## Completion Criteria
## Allowed Edit Scope
## Forbidden Scope
## Implementation Steps
## Verification Plan
## Stop Conditions
```

## Implementation

After the planner handoff is complete:

1. Write the planner's returned handoff to `.claude/state/handoff.md`.
2. Read the `## Verdict` line and write it to `.claude/state/complexity_verdict.txt` (single word: `light` or `standard`).
3. Delete `.claude/state/.edit_context_injected` if it exists.
4. Present the handoff summary to the user.
5. Ask whether to start implementation now.
6. Wait for explicit user confirmation before spawning the implementer.
7. If confirmed, spawn `implementer-sonnet`:
   - "Read the handoff from `.claude/state/handoff.md` and execute it."
   - Do NOT copy the handoff text into the prompt.
8. After the implementer returns, report: touched files, verification results, open risks.

## Continue to finish (optional)

After implementation completes successfully:

1. Ask: "Implementation complete. Proceed with review and commit?"
2. If the user confirms, proceed with the `ado-finish-task` flow inline.
3. If the user declines, remind the user to say "finish" when ready.

When chaining into the finish flow:
- If `.claude/state/complexity_verdict.txt` contains `light`: reviewer is skipped automatically.
- If `standard` or file missing: full reviewer flow applies.
- A reviewer skip does NOT remove the user confirmation gate before commit.

## Final output of this skill

Before ending, report:

1. selected work item
2. whether start approval was granted
3. state transition result
4. created branch
5. planner handoff summary
6. implementer result (touched files, verification results, open risks) — or a note that implementation was deferred
7. finish flow result (reviewer verdict, commit, PR URL) — or a note that finish was deferred
8. branch base verification result against `origin/{{BASE_BRANCH}}`
