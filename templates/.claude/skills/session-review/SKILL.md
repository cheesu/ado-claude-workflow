---
name: session-review
description: Shortcut alias for generating a session review report. Use when the user says "session review", "리뷰 리포트", "세션 분석", or asks to analyze how a task session went.
user-invocable: true
---

# Session Review

Follow `ado-session-review` exactly.

If the user included a task number, use it.
If not, infer from the current branch.

Default depth is `full` unless the user says "summary" or "간단히".
