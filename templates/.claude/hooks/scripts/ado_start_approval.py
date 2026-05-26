#!/usr/bin/env python3
"""
CLI tool — issues a start approval token that allows branch creation and ADO state updates.
TTL: 1 hour by default.

Usage:
  python3 ado_start_approval.py approve --repo <path> --branch-type <type> --work-item <id>
  python3 ado_start_approval.py show
  python3 ado_start_approval.py clear
"""

import argparse
import json
import sys
import time
from pathlib import Path


STATE_PATH = Path(__file__).resolve().parents[3] / '.claude' / 'state' / 'ado_start_approval.json'


def approve(args: argparse.Namespace) -> int:
  state = {
    'repo': str(Path(args.repo).resolve()),
    'branch_type': args.branch_type,
    'work_item': args.work_item,
    'approved_at': int(time.time()),
    'expires_at': int(time.time()) + args.ttl_seconds,
  }
  STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
  STATE_PATH.write_text(json.dumps(state, indent=2), encoding='utf-8')
  print(json.dumps(state, indent=2))
  return 0


def show(_: argparse.Namespace) -> int:
  if not STATE_PATH.exists():
    print('{}')
    return 0
  print(STATE_PATH.read_text(encoding='utf-8'))
  return 0


def clear(_: argparse.Namespace) -> int:
  if STATE_PATH.exists():
    STATE_PATH.unlink()
  print('{}')
  return 0


def build_parser() -> argparse.ArgumentParser:
  parser = argparse.ArgumentParser(
    description='Manage ADO pickup approval state for Claude Code hooks.',
  )
  subparsers = parser.add_subparsers(dest='command', required=True)

  approve_parser = subparsers.add_parser('approve')
  approve_parser.add_argument('--repo', required=True)
  approve_parser.add_argument('--branch-type', required=True)
  approve_parser.add_argument('--work-item', required=True)
  approve_parser.add_argument('--ttl-seconds', type=int, default=3600)
  approve_parser.set_defaults(func=approve)

  show_parser = subparsers.add_parser('show')
  show_parser.set_defaults(func=show)

  clear_parser = subparsers.add_parser('clear')
  clear_parser.set_defaults(func=clear)

  return parser


def main() -> int:
  parser = build_parser()
  args = parser.parse_args()
  return args.func(args)


if __name__ == '__main__':
  sys.exit(main())
