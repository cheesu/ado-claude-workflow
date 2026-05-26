#!/usr/bin/env python3
"""
PreToolUse hook — blocks edits to forbidden paths.
Configured by install.sh: forbidden prefixes are substituted at install time.
"""

import json
import sys
from pathlib import Path


# Resolved from script location: scripts/ → hooks/ → .claude/ → frontend/
FRONTEND_ROOT = Path(__file__).resolve().parents[3]

FORBIDDEN_PREFIXES = [
{{FORBIDDEN_PREFIXES_LIST}}
]


def deny(reason: str) -> int:
  payload = {
    'hookSpecificOutput': {
      'hookEventName': 'PreToolUse',
      'permissionDecision': 'deny',
      'permissionDecisionReason': reason,
    },
  }
  print(json.dumps(payload))
  return 0


def main() -> int:
  raw = sys.stdin.read().strip() or '{}'
  event = json.loads(raw)
  tool_input = event.get('tool_input', {})
  cwd = Path(event.get('cwd', '/')).resolve()

  file_path = tool_input.get('file_path') or tool_input.get('path')
  if not file_path:
    return 0

  target = Path(file_path).expanduser().resolve()
  if FRONTEND_ROOT not in target.parents and target != FRONTEND_ROOT:
    return 0

  if FRONTEND_ROOT not in cwd.parents and cwd != FRONTEND_ROOT:
    return 0

  for forbidden in FORBIDDEN_PREFIXES:
    if target == forbidden or forbidden in target.parents:
      return deny(
        f'ADO workflow harness blocks edits to {forbidden}. '
        'Use product-scoped files under {{WORK_PATH}}/ instead.',
      )

  return 0


if __name__ == '__main__':
  try:
    sys.exit(main())
  except Exception as exc:
    payload = {
      'hookSpecificOutput': {
        'hookEventName': 'PreToolUse',
        'permissionDecision': 'deny',
        'permissionDecisionReason': (
          f'[GUARD:error] ado_protect_paths failed unexpectedly '
          f'({type(exc).__name__}: {exc}). Fix the hook script before proceeding.'
        ),
      },
    }
    print(json.dumps(payload))
    sys.exit(0)
