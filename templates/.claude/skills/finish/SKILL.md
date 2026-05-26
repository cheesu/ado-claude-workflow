---
name: finish
description: Shortcut alias for the ADO finish flow. Use when the user says finish, wrap up, commit, or asks to close out an ADO frontend work item with review, approval, commit, push, and Draft PR.
user-invocable: true
---

# Finish

Load `ado-guardrails`, then follow `ado-finish-task` exactly.
If the user included a number, treat it as the work item number.
If no number, inspect the current branch and diff to proceed.
