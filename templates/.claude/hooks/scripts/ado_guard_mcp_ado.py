#!/usr/bin/env python3
"""
PreToolUse hook for Azure DevOps MCP mutating tools.
Ensures approval tokens are valid before allowing state-changing MCP operations.
This closes the gap where MCP tool calls bypass the Bash-only ado_guard_shell.py.
"""

import json
import sys
import time
from pathlib import Path


# Resolved from script location: scripts/ → hooks/ → .claude/ → frontend/
FRONTEND_ROOT = Path(__file__).resolve().parents[3]
REPO_ROOT = Path(__file__).resolve().parents[4]

START_APPROVAL_PATH = FRONTEND_ROOT / '.claude' / 'state' / 'ado_start_approval.json'
FINISH_APPROVAL_PATH = FRONTEND_ROOT / '.claude' / 'state' / 'ado_finish_approval.json'

# Tools that require start approval
START_APPROVAL_TOOLS = {
  'mcp__azure-devops__wit_update_work_item',
  'mcp__azure-devops__repo_create_branch',
}

# Tools that require finish approval
FINISH_APPROVAL_TOOLS = {
  'mcp__azure-devops__repo_create_pull_request',
}


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


def load_json_state(path: Path) -> dict:
  if not path.exists():
    return {}
  try:
    return json.loads(path.read_text(encoding='utf-8'))
  except json.JSONDecodeError:
    return {}


def token_is_valid(state: dict) -> bool:
  if not state:
    return False
  if state.get('repo') != str(REPO_ROOT):
    return False
  if int(state.get('expires_at', 0)) < int(time.time()):
    return False
  return True


def main() -> int:
  raw = sys.stdin.read().strip() or '{}'
  event = json.loads(raw)
  tool_name = event.get('tool_name', '')
  cwd = Path(event.get('cwd', '/')).resolve()

  # Only guard when running from the frontend directory
  if FRONTEND_ROOT not in cwd.parents and cwd != FRONTEND_ROOT:
    return 0

  if tool_name in START_APPROVAL_TOOLS:
    state = load_json_state(START_APPROVAL_PATH)
    if not token_is_valid(state):
      return deny(
        f'[GUARD:mcp_start_approval] {tool_name} is blocked until the user '
        'confirms task start and ado_start_approval.py approve is executed. '
        f'Re-approve: python3 ".claude/hooks/scripts/ado_start_approval.py" approve '
        f'--repo {REPO_ROOT} --branch-type <type> --work-item <number>'
      )

  if tool_name in FINISH_APPROVAL_TOOLS:
    state = load_json_state(FINISH_APPROVAL_PATH)
    if not token_is_valid(state):
      return deny(
        f'[GUARD:mcp_completion_approval] {tool_name} is blocked until the user '
        'confirms task completion and ado_finish_approval.py approve is executed. '
        f'Re-approve: python3 ".claude/hooks/scripts/ado_finish_approval.py" approve '
        f'--repo {REPO_ROOT} --branch "$(git branch --show-current)" --work-item <number>'
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
          f'[GUARD:error] ado_guard_mcp_ado failed unexpectedly '
          f'({type(exc).__name__}: {exc}). Fix the hook script before proceeding.'
        ),
      },
    }
    print(json.dumps(payload))
    sys.exit(0)
