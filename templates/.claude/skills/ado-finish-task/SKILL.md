---
name: ado-finish-task
description: Finish an ADO frontend task. Use when the user wants final review, explicit completion confirmation, commit creation, push, and Draft PR creation to {{BASE_BRANCH}}.
user-invocable: true
---

# ADO Finish Task

Use this workflow when the implementation is ready for final verification in `{{FRONTEND_ROOT}}`.

Always load the `ado-guardrails` skill first.

## Goal

Close the loop safely:

1. Review the implemented change.
2. Re-run verification.
3. Get explicit user confirmation that the task is complete.
4. Commit with the configured format.
5. Push the work branch.
6. Create a Draft PR to `{{BASE_BRANCH}}`.

## Complexity verdict check

Before anything else, check if a planner-declared complexity verdict exists:

```bash
cat "{{FRONTEND_ROOT}}/.claude/state/complexity_verdict.txt" 2>/dev/null || echo "standard"
```

- If result is `light`: **skip the reviewer entirely** — proceed directly to the Verification baseline section after preflight passes.
- If result is `standard` or file missing: run the full reviewer flow as normal.

Note: Skipping the reviewer does NOT skip the user confirmation gate before commit.

## Deterministic preflight

Before spawning the reviewer (Opus), run a cheap preflight check:

```bash
# 1. Verify branch pattern
BRANCH=$(git branch --show-current)
echo "$BRANCH" | grep -qE '^{{BRANCH_PREFIX}}/(feature|fix|refactor|update|test|docs|chore)/[0-9]+$' || echo "PREFLIGHT FAIL: branch pattern"

# 2. Check no forbidden paths were touched
git diff --name-only | grep -qE '^src/(pages|shared)/' && echo "PREFLIGHT FAIL: forbidden path touched" || true

# 3. Type check
cd "{{FRONTEND_ROOT}}" && yarn tsc --noEmit

# 4. Lint
cd "{{FRONTEND_ROOT}}" && yarn lint
```

If any preflight check fails, report the failure to the user immediately — do not spawn `reviewer-opus-4_6`.

## Required review flow

1. Inspect git state:
   - `git branch --show-current`
   - `git status`
   - `git diff --cached`
   - `git diff`
2. Spawn `reviewer-opus-4_6`.
3. The reviewer must answer:
   - Does the diff satisfy the handoff?
   - Did the change stay inside allowed paths?
   - What tests or checks still need to run?
   - What risks remain?

## Reviewer verdict handling

- **ready**: proceed directly to the verification baseline and user confirmation gate.
- **ready with caveats**: show the caveats to the user, then proceed to the user confirmation gate.
- **not ready**:
  1. Show the reviewer's findings to the user.
  2. Ask: "Review found issues that need fixing. Fix now?"
  3. If the user confirms:
     a. Write the reviewer's findings to `.claude/state/review_findings.md`.
     b. Spawn `implementer-sonnet` with:
        - "Read the review findings from `.claude/state/review_findings.md` and the original handoff from `.claude/state/handoff.md`. Fix the issues identified by the reviewer."
  4. After the implementer returns, re-run verification and spawn `reviewer-opus-4_6` once more.
  5. If the second review is still **not ready**, stop and report — do not loop again.
  6. If the user declines to fix, ask whether to proceed anyway or abandon the finish flow.

## Verification baseline

Run verification from `{{FRONTEND_ROOT}}`.

Prefer scoped lint on changed files only:

```bash
yarn eslint $(git diff --name-only | grep -E '\.(ts|tsx)$' | tr '\n' ' ')
```

Always run type checking in addition to lint:

```bash
yarn tsc --noEmit
```

If verification fails, do not proceed to commit or PR creation.

## User confirmation gate

Before any commit, push, or PR action:

1. Summarize what changed.
2. Summarize verification results.
3. Ask the user whether the task is complete.
4. Proceed only after a clear approval.

After approval, write the approval token:

```bash
python3 "{{FRONTEND_ROOT}}/.claude/hooks/scripts/ado_finish_approval.py" approve \
  --repo {{REPO_ROOT}} \
  --branch "$(git branch --show-current)" \
  --work-item <taskNumber>
```

## Commit format

```text
[{{PRODUCT_CODE}}][{{SCOPE_CODE}}]<emoji><type>: <subject> [#work-item]
```

Type and emoji mapping:

- `✨feat`
- `🐛fix`
- `♻️refactor`
- `💄feat`
- `🌐update`
- `📦update`
- `✅test`
- `📝docs`
- `🔧chore`
- `🔥remove`

Keep the subject factual, concise, and in current-tense style.

## Commit execution

1. Stage only the relevant files.
2. Show the proposed commit message first.
3. Commit only after approval has been granted.

```bash
git commit -m "$(cat <<'EOF'
[{{PRODUCT_CODE}}][{{SCOPE_CODE}}]🐛fix: example title [#12345]
EOF
)"
```

## Draft PR rules

- Source branch: current `{{BRANCH_PREFIX}}/{type}/{taskNumber}`
- Target branch: `{{BASE_BRANCH}}`
- Create as Draft

```bash
az repos pr create \
  --source-branch "$(git branch --show-current)" \
  --target-branch {{BASE_BRANCH}} \
  --title "<PR title>" \
  --description "$(cat <<'EOF'
## Summary
<!--- Describe why this change is needed and what problem it solves. -->
- Description
    - NA
- Intent
    - NA
- Effects
    - NA

## Related Work Item
<!--- Link the work item here -->

## PR Checklist
- [ ] I have reviewed my own code.
- [ ] I have added comments where the logic is not obvious.
- [ ] I have added or updated tests that prove this fix/feature works.

## Screenshots (if applicable)
EOF
)" \
  --draft true
```

## Fallback order

1. Azure DevOps MCP
2. `az repos pr create`
3. If PR creation cannot run, print the exact manual command or URL for the user

## Final output of this skill

Before ending, report:

1. reviewer verdict
2. verification results
3. user approval status
4. final commit message
5. branch push result
6. Draft PR URL or fallback instruction
