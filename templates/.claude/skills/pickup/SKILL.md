---
name: pickup
description: Shortcut alias for the ADO pickup flow. Use when the user says pickup, start task, or asks to begin an assigned ADO frontend work item.
user-invocable: true
---

# Pickup

Load `ado-guardrails`, then follow `ado-pickup-task` exactly.
If the user included a number, treat it as the work item candidate.
If vague, list assigned work items first.
