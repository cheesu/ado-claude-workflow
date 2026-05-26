#!/usr/bin/env python3
"""
PostToolUse hook — injects a verification reminder after the first edit in a session.
"""

import json
import sys
from pathlib import Path


# Resolved from script location: scripts/ → hooks/ → .claude/ → frontend/
FRONTEND_ROOT = Path(__file__).resolve().parents[3]

# Watch the configured work path and locales
WORK_PATH_PARTS = '{{WORK_PATH}}'.split('/')
WATCH_PREFIXES = [
  FRONTEND_ROOT.joinpath(*WORK_PATH_PARTS),
  FRONTEND_ROOT / 'src' / 'locales',
]
INJECTED_FLAG = FRONTEND_ROOT / '.claude' / 'state' / '.edit_context_injected'


def main() -> int:
  raw = sys.stdin.read().strip() or '{}'
  event = json.loads(raw)
  tool_input = event.get('tool_input', {})
  file_path = tool_input.get('file_path') or tool_input.get('path')
  if not file_path:
    return 0

  target = Path(file_path).expanduser().resolve()
  if not any(target == prefix or prefix in target.parents for prefix in WATCH_PREFIXES):
    return 0

  # Only inject the context reminder once per work session.
  # The flag is reset by the pickup skill at the start of each new task.
  if INJECTED_FLAG.exists():
    return 0

  INJECTED_FLAG.parent.mkdir(parents=True, exist_ok=True)
  INJECTED_FLAG.touch()

  payload = {
    'hookSpecificOutput': {
      'hookEventName': 'PostToolUse',
      'additionalContext': (
        '{{PRODUCT_CODE}} frontend file edited. Before declaring completion, keep changes '
        'inside the allowed scope and run verification (yarn lint + yarn tsc --noEmit) from '
        f'{FRONTEND_ROOT}.'
      ),
    },
  }
  print(json.dumps(payload))
  return 0


if __name__ == '__main__':
  try:
    sys.exit(main())
  except Exception:
    # fail-open: context injection is non-critical; do not block on error
    sys.exit(0)
