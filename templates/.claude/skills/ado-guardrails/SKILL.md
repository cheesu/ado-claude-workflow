---
name: ado-guardrails
description: Apply ADO workflow working rules for a frontend project. Use when editing product frontend code, generating commit or PR text, or deciding whether a file or branch is allowed.
disable-model-invocation: true
---

# ADO Workflow Guardrails

Use these rules for {{PRODUCT_CODE}} frontend work in `{{FRONTEND_ROOT}}`.

## Repository anchors

- Repo root: `{{REPO_ROOT}}`
- Frontend root: `{{FRONTEND_ROOT}}`
- Product work root: `{{WORK_PATH}}/`

## User-facing language

- Write user-facing questions, confirmation prompts, progress updates, and summaries in Korean by default.
- Switch away from Korean only when the user explicitly asks for another language.
- Keep commit messages, PR titles, and PR bodies in English per the repo commit guide.

## Edit guardrails

- Never edit `src/pages/` for this workflow.
- Never edit `src/shared/` for this workflow.
- Default to `{{WORK_PATH}}/` for product code changes.
- `src/locales/` is allowed when UI text or i18n keys need updates.
- Reuse existing shared utilities instead of changing shared code.
- Follow frontend style already used in the repo:
  - single quotes
  - no semicolons
  - TypeScript strict-friendly changes
  - i18n for user-facing strings

## Project-specific rules

Add any project-specific conventions here after installation — for example:
- Design token usage (e.g. use design system tokens instead of hardcoded style values)
- Naming conventions specific to this codebase
- Patterns to avoid or prefer in this product
- Any other rules the team enforces beyond the defaults above

## Branch rules

- Base branch: `{{BASE_BRANCH}}`
- Allowed work branch shapes:
  - `{{BRANCH_PREFIX}}/feature/{taskNumber}`
  - `{{BRANCH_PREFIX}}/fix/{taskNumber}`
  - `{{BRANCH_PREFIX}}/refactor/{taskNumber}`
  - `{{BRANCH_PREFIX}}/update/{taskNumber}`
  - `{{BRANCH_PREFIX}}/test/{taskNumber}`
  - `{{BRANCH_PREFIX}}/docs/{taskNumber}`
  - `{{BRANCH_PREFIX}}/chore/{taskNumber}`

Choose the branch type from the actual change:

- new user-facing functionality → `feature`
- bug fix → `fix`
- behavior-preserving cleanup → `refactor`
- dependency or resource update → `update`
- tests only → `test`
- docs only → `docs`
- tooling or config → `chore`

## Commit and PR rules

- Commit and PR title format:
  - `[{{PRODUCT_CODE}}][{{SCOPE_CODE}}]<emoji><type>: <subject> [#work-item]`
- Keep the subject factual and short, in current-tense style.
- Use the strict emoji/type mapping:
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
- Draft PR target branch is always `{{BASE_BRANCH}}`.
- New work branches must be created only after `{{BASE_BRANCH}}` is checked out, updated with `git pull --ff-only origin {{BASE_BRANCH}}`, and verified to match `origin/{{BASE_BRANCH}}`.
- Do not create new work branches from `main`, `origin/main`, or any existing task branch.
- If reusing an existing work branch, verify first that its ancestry is rooted in the `{{BASE_BRANCH}}` line rather than a shared split point with `origin/main`.

## Verification baseline

Before claiming completion:

1. Review the changed paths and confirm they stay inside the allowed scope.
2. Run frontend verification from `{{FRONTEND_ROOT}}`.
3. At minimum run `yarn lint` and `yarn tsc --noEmit` unless a narrower validated command is clearly better.
4. Add task-specific checks for risky viewer, result, edit, or i18n changes.
5. Do not commit or create a PR until the user explicitly confirms completion.

## Azure DevOps flow

- Azure DevOps organization: `https://dev.azure.com/{{ADO_ORG}}`
- Azure DevOps project: `{{ADO_PROJECT}}`
- Prefer Azure DevOps MCP when available and authenticated.
- Fall back to Azure CLI with the `azure-devops` extension when MCP is unavailable.
- Never store org URLs, PATs, or personal defaults in tracked repo files.

## Token efficiency guidance

- For large TypeScript or React files, prefer Serena semantic symbol tools before reading full files.
- Use Serena first for:
  - symbol lookup
  - references/usages
  - file outline or overview
  - narrow body-level reads
- Fall back to `Read`, `Glob`, or `Grep` when Serena is unavailable or when plain text search is clearly simpler.
- Avoid broad whole-file reads when only one hook, component, or function body is needed.
