#!/usr/bin/env python3
"""
PreToolUse hook — shell command gate.
Blocks destructive git commands, enforces branch naming, validates approval tokens
before commit/push/PR, and prevents staging of local-only config files.
"""

import json
import re
import subprocess
import sys
import time
from pathlib import Path


# Resolved from script location: scripts/ → hooks/ → .claude/ → frontend/
FRONTEND_ROOT = Path(__file__).resolve().parents[3]
REPO_ROOT = Path(__file__).resolve().parents[4]

START_APPROVAL_PATH = FRONTEND_ROOT / '.claude' / 'state' / 'ado_start_approval.json'
STATE_PATH = FRONTEND_ROOT / '.claude' / 'state' / 'ado_finish_approval.json'

BRANCH_RE = re.compile(
  r'^{{BRANCH_PREFIX}}/(feature|fix|refactor|update|test|docs|chore)/\d+$',
)

# Files that exist only locally and must never be committed
PROTECTED_LOCAL_ONLY_PATHS = {
  '.gitignore',
  'frontend/.claude/settings.local.json',
  'frontend/.cursor/rules/commit_pr_guide.mdc',
  # Add project-specific local-only files here
}

DESTRUCTIVE_PATTERNS = [
  re.compile(r'(^|[;&\s])git\s+reset\s+--hard(\s|$)', re.IGNORECASE),
  re.compile(r'(^|[;&\s])git\s+checkout\s+--(\s|$)', re.IGNORECASE),
  re.compile(r'(^|[;&\s])git\s+clean\s+-f[dx]?(\s|$)', re.IGNORECASE),
  re.compile(r'(^|[;&\s])git\s+push(?:\s+\S+)*\s+--force(\s|$)', re.IGNORECASE),
  re.compile(r'(^|[;&\s])git\s+push(?:\s+\S+)*\s+-f(\s|$)', re.IGNORECASE),
  # Force-delete local branch
  re.compile(r'(^|[;&\s])git\s+branch\s+(-D|--delete\s+-f|--delete\s+--force)\s+\S', re.IGNORECASE),
  # Delete remote branch via refspec
  re.compile(r'(^|[;&\s])git\s+push\s+\S+\s+:\S', re.IGNORECASE),
]


def respond(reason: str) -> int:
  payload = {
    'hookSpecificOutput': {
      'hookEventName': 'PreToolUse',
      'permissionDecision': 'deny',
      'permissionDecisionReason': reason,
    },
  }
  print(json.dumps(payload))
  return 0


def current_branch(cwd: Path) -> str:
  result = subprocess.run(
    ['git', '-C', str(cwd), 'branch', '--show-current'],
    check=False, capture_output=True, text=True,
  )
  return result.stdout.strip()


def git_output(cwd: Path, *args: str) -> str:
  result = subprocess.run(
    ['git', '-C', str(cwd), *args],
    check=False, capture_output=True, text=True,
  )
  return result.stdout.strip()


def worktree_is_clean(cwd: Path) -> bool:
  return not git_output(cwd, 'status', '--short')


def head_matches_remote_base(cwd: Path) -> bool:
  local_head = git_output(cwd, 'rev-parse', 'HEAD')
  remote_head = git_output(cwd, 'rev-parse', f'origin/{{BASE_BRANCH}}')
  return bool(local_head) and local_head == remote_head


def extract_created_branches(command: str) -> list[str]:
  patterns = (
    re.compile(r'(?:^|[;&|]\s*)git\s+checkout\s+-b\s+([^\s;&|]+)'),
    re.compile(r'(?:^|[;&|]\s*)git\s+switch\s+-c\s+([^\s;&|]+)'),
  )
  matches: list[str] = []
  for pattern in patterns:
    matches.extend(pattern.findall(command))
  return matches


def load_state() -> dict:
  if not STATE_PATH.exists():
    return {}
  try:
    return json.loads(STATE_PATH.read_text(encoding='utf-8'))
  except json.JSONDecodeError:
    return {}


def load_start_state() -> dict:
  if not START_APPROVAL_PATH.exists():
    return {}
  try:
    return json.loads(START_APPROVAL_PATH.read_text(encoding='utf-8'))
  except json.JSONDecodeError:
    return {}


def approval_is_valid(cwd: Path, branch: str) -> bool:
  state = load_state()
  if not state:
    return False
  if state.get('repo') != str(REPO_ROOT):
    return False
  if state.get('branch') != branch:
    return False
  if int(state.get('expires_at', 0)) < int(time.time()):
    return False
  return cwd == FRONTEND_ROOT or FRONTEND_ROOT in cwd.parents


def start_approval_is_valid(cwd: Path, branch_name: str) -> bool:
  state = load_start_state()
  if not state:
    return False
  if state.get('repo') != str(REPO_ROOT):
    return False
  if int(state.get('expires_at', 0)) < int(time.time()):
    return False
  if not (cwd == FRONTEND_ROOT or FRONTEND_ROOT in cwd.parents):
    return False

  match = BRANCH_RE.match(branch_name)
  if not match:
    return False

  branch_type = match.group(1)
  task_number = branch_name.rsplit('/', 1)[-1]
  return (
    state.get('branch_type') == branch_type
    and str(state.get('work_item')) == task_number
  )


def start_state_matches_work_item(cwd: Path, command: str) -> bool:
  state = load_start_state()
  if not state:
    return False
  if state.get('repo') != str(REPO_ROOT):
    return False
  if int(state.get('expires_at', 0)) < int(time.time()):
    return False
  if not (cwd == FRONTEND_ROOT or FRONTEND_ROOT in cwd.parents):
    return False

  match = re.search(r'--id\s+(\d+)', command)
  if not match:
    return False

  return str(state.get('work_item')) == match.group(1)


def staged_protected_paths(cwd: Path) -> list[str]:
  result = subprocess.run(
    ['git', '-C', str(cwd), 'diff', '--cached', '--name-only'],
    check=False, capture_output=True, text=True,
  )
  staged_paths = [line.strip() for line in result.stdout.splitlines() if line.strip()]
  return [path for path in staged_paths if path in PROTECTED_LOCAL_ONLY_PATHS]


def command_requires_approval(command: str) -> bool:
  lowered = command.lower()
  return (
    'git commit' in lowered
    or lowered.startswith('git commit')
    or 'git push' in lowered
    or 'az repos pr create' in lowered
  )


def strip_leading_cd_wrapper(command: str) -> str:
  match = re.match(
    r'^\s*cd\s+(?:"[^"]+"|\'[^\']+\'|\S+)\s*&&\s*(.+)$',
    command, re.DOTALL,
  )
  if not match:
    return command
  return match.group(1).strip()


def branch_creation_uses_compound_git_chain(command: str) -> bool:
  effective_command = strip_leading_cd_wrapper(command)
  return (
    '&&' in effective_command
    or ';' in effective_command
    or '||' in effective_command
    or '\n' in effective_command
  )


def validate_branch_creation(cwd: Path, command: str) -> str:
  created_branches = extract_created_branches(command)
  if not created_branches:
    return ''

  if len(created_branches) > 1:
    return '[GUARD:branch_creation] Create at most one work branch per shell command.'

  created_branch = created_branches[0]
  if not BRANCH_RE.match(created_branch):
    return (
      '[GUARD:branch_creation] New work branches must match '
      '{{BRANCH_PREFIX}}/{feature|fix|refactor|update|test|docs|chore}/{taskNumber}.'
    )
  if branch_creation_uses_compound_git_chain(command):
    return (
      '[GUARD:branch_creation] Create work branches in a dedicated git command after separately '
      'checking out and updating {{BASE_BRANCH}}.'
    )

  base_branch = current_branch(cwd)
  if base_branch != '{{BASE_BRANCH}}':
    return (
      '[GUARD:branch_creation] New work branches can only be created while currently on '
      '{{BASE_BRANCH}}.'
    )
  if not worktree_is_clean(cwd):
    return (
      '[GUARD:branch_creation] New work branches can only be created from a clean working tree on '
      '{{BASE_BRANCH}}.'
    )
  if not head_matches_remote_base(cwd):
    return (
      '[GUARD:branch_creation] {{BASE_BRANCH}} must first match origin/{{BASE_BRANCH}} before a new '
      'work branch can be created.'
    )
  if not start_approval_is_valid(cwd, created_branch):
    return (
      '[GUARD:start_approval] Creating a new work branch from {{BASE_BRANCH}} is blocked until '
      'the user confirms task start and ado_start_approval.py approve is executed. '
      'Re-approve: python3 ".claude/hooks/scripts/ado_start_approval.py" approve '
      f'--repo {REPO_ROOT} --branch-type <type> --work-item <number>'
    )

  return ''


def validate_work_item_state_update(cwd: Path, command: str) -> str:
  lowered = command.lower()
  if 'az boards work-item update' not in lowered:
    return ''
  if start_state_matches_work_item(cwd, command):
    return ''
  return (
    '[GUARD:start_approval] Updating Azure DevOps work item state is blocked until '
    'the user confirms task start for the selected work item. '
    'Re-approve: python3 ".claude/hooks/scripts/ado_start_approval.py" approve '
    f'--repo {REPO_ROOT} --branch-type <type> --work-item <number>'
  )


def validate_completion_approval(cwd: Path, command: str) -> str:
  if not command_requires_approval(command):
    return ''

  protected_paths = staged_protected_paths(cwd)
  if protected_paths:
    joined = ', '.join(protected_paths)
    return (
      '[GUARD:protected_files] The following local-only files are staged and blocked from commit: '
      f'{joined}. Unstage them before continuing.'
    )

  branch = current_branch(cwd)
  if not BRANCH_RE.match(branch):
    return f'[GUARD:branch_pattern] Current branch "{branch}" does not match the work branch pattern.'
  if approval_is_valid(cwd, branch):
    return ''
  return (
    '[GUARD:completion_approval] Commit, push, and PR creation are blocked until the user confirms task '
    'completion and ado_finish_approval.py approve is executed. '
    'Re-approve: python3 ".claude/hooks/scripts/ado_finish_approval.py" approve '
    f'--repo {REPO_ROOT} --branch "$(git branch --show-current)" --work-item <number>'
  )


def validate_pr_create(command: str) -> str:
  lowered = command.lower()
  if 'az repos pr create' not in lowered:
    return ''
  if '--target-branch {{BASE_BRANCH}}' not in command:
    return '[GUARD:pr_target] Draft PR target branch must be {{BASE_BRANCH}}.'
  if '--draft' not in lowered:
    return '[GUARD:pr_draft] ADO workflow harness requires Draft PR creation.'
  return ''


def main() -> int:
  raw = sys.stdin.read().strip() or '{}'
  event = json.loads(raw)
  cwd = Path(event.get('cwd', '/')).resolve()
  command = (event.get('tool_input', {}) or {}).get('command', '')
  if not command:
    return 0

  if FRONTEND_ROOT not in cwd.parents and cwd != FRONTEND_ROOT:
    return 0

  for pattern in DESTRUCTIVE_PATTERNS:
    if pattern.search(command):
      return respond('[GUARD:destructive] ADO workflow harness blocked a destructive git command.')

  for validator in (
    validate_branch_creation,
    validate_work_item_state_update,
    validate_completion_approval,
    lambda _cwd, current_command: validate_pr_create(current_command),
  ):
    reason = validator(cwd, command)
    if reason:
      return respond(reason)

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
          f'[GUARD:error] ado_guard_shell failed unexpectedly '
          f'({type(exc).__name__}: {exc}). Fix the hook script before proceeding.'
        ),
      },
    }
    print(json.dumps(payload))
    sys.exit(0)
