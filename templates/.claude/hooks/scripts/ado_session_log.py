#!/usr/bin/env python3
"""
ado_session_log.py

ADO workflow session log generator.
Parses the subagent JSONL files saved by Claude Code to calculate
accurate tool call counts and token usage per agent, then writes
.claude/logs/tasks/{taskNumber}_{YYYYMMDD}.md.

Usage:
  python3 ado_session_log.py analyze \
    --task-number <taskNumber> \
    [--session-id <sessionId>] \
    [--project-dir /path/to/frontend]

Auto-detect latest session:
  python3 ado_session_log.py analyze \
    --task-number <taskNumber> \
    --auto-session
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path


# Resolved from script location: scripts/ -> hooks/ -> .claude/ -> frontend/
FRONTEND_ROOT = Path(__file__).resolve().parents[3]

EXPLORE_TOOLS = {"Read", "Grep", "Glob", "Bash"}
IMPLEMENT_TOOLS = {"Edit", "Write", "MultiEdit"}
VERIFY_TOOLS = {"Bash"}

CLAUDE_BASE = Path.home() / ".claude" / "projects"


def find_project_slug(project_dir: str) -> str:
    """Convert a project path to the Claude project slug format."""
    path = Path(project_dir).resolve()
    slug = str(path).replace("/", "-")
    if slug.startswith("-"):
        slug = slug[1:]
    return "-" + slug


def find_session_dir(project_dir: str, session_id=None, auto: bool = False):
    slug = find_project_slug(project_dir)
    base = CLAUDE_BASE / slug

    if not base.exists():
        # Fallback: match by path suffix
        target_suffix = str(Path(project_dir).resolve()).replace("/", "-").lstrip("-")
        for candidate in CLAUDE_BASE.iterdir():
            if candidate.name.endswith(target_suffix):
                base = candidate
                break
        else:
            return None

    if session_id:
        p = base / session_id
        return p if p.exists() else None

    if auto:
        sessions = []
        for d in base.iterdir():
            if d.is_dir() and (d / "subagents").exists():
                try:
                    mtime = max(f.stat().st_mtime for f in (d / "subagents").iterdir())
                    sessions.append((mtime, d))
                except Exception:
                    pass
        if sessions:
            sessions.sort(key=lambda x: -x[0])
            return sessions[0][1]

    return None


def tool_detail(name: str, inp: dict, src_prefix: str) -> str:
    """Summarize a tool call's key arguments in one line."""
    def shorten(path: str) -> str:
        return path.replace(src_prefix, "") if path else path

    if name == "Read":
        p = shorten(inp.get("file_path", ""))
        offset = inp.get("offset")
        limit = inp.get("limit")
        suffix = f" (L{offset}~{offset+limit})" if offset and limit else ""
        return f"{p}{suffix}"
    if name in ("Edit", "MultiEdit", "Write"):
        return shorten(inp.get("file_path", ""))
    if name == "Grep":
        pattern = inp.get("pattern", "")
        path = shorten(inp.get("path", ""))
        return f'"{pattern}" in {path}' if path else f'"{pattern}"'
    if name == "Glob":
        return inp.get("pattern", "")
    if name == "Bash":
        cmd = inp.get("command", "")
        first = cmd.split("\n")[0].strip()
        return first[:80] + ("…" if len(first) > 80 else "")
    keys = list(inp.keys())
    if keys:
        first_val = str(inp[keys[0]])[:60]
        return f"{keys[0]}={first_val}"
    return ""


def parse_subagent(jsonl_path: Path, meta_path: Path, src_prefix: str) -> dict:
    """Parse a subagent JSONL file and return usage statistics."""
    meta = {}
    if meta_path.exists():
        with open(meta_path) as f:
            meta = json.load(f)

    tool_sequence = []   # (call_idx, tool_name, detail_str)
    token_per_call = []  # per API call: {idx, input, output, cache_read, cache_create, tools}

    with open(jsonl_path) as f:
        lines = [json.loads(l.strip()) for l in f if l.strip()]

    call_idx = 0
    for entry in lines:
        msg = entry.get("message", {})
        if not isinstance(msg, dict):
            continue

        usage = msg.get("usage")
        content = msg.get("content", [])
        if not isinstance(content, list):
            content = []

        tools_in_call = []
        for c in content:
            if isinstance(c, dict) and c.get("type") == "tool_use":
                name = c.get("name", "unknown")
                detail = tool_detail(name, c.get("input", {}), src_prefix)
                tools_in_call.append(name)
                tool_sequence.append((call_idx, name, detail))

        if usage:
            token_per_call.append({
                "idx": call_idx,
                "input": usage.get("input_tokens", 0),
                "output": usage.get("output_tokens", 0),
                "cache_read": usage.get("cache_read_input_tokens", 0),
                "cache_create": usage.get("cache_creation_input_tokens", 0),
                "tools": tools_in_call,
            })
            call_idx += 1

    tool_counts: dict[str, int] = {}
    for _, name, _ in tool_sequence:
        tool_counts[name] = tool_counts.get(name, 0) + 1

    phase_tokens: dict[str, dict] = {
        "explore":   {"input": 0, "output": 0, "cache_read": 0, "cache_create": 0},
        "implement": {"input": 0, "output": 0, "cache_read": 0, "cache_create": 0},
        "verify":    {"input": 0, "output": 0, "cache_read": 0, "cache_create": 0},
        "other":     {"input": 0, "output": 0, "cache_read": 0, "cache_create": 0},
    }

    first_edit_call_idx = None
    last_edit_call_idx = None
    for tc in token_per_call:
        if any(t in IMPLEMENT_TOOLS for t in tc["tools"]):
            if first_edit_call_idx is None:
                first_edit_call_idx = tc["idx"]
            last_edit_call_idx = tc["idx"]

    for tc in token_per_call:
        if any(t in IMPLEMENT_TOOLS for t in tc["tools"]):
            phase = "implement"
        elif first_edit_call_idx is None or tc["idx"] < first_edit_call_idx:
            phase = "explore"
        elif last_edit_call_idx is not None and tc["idx"] > last_edit_call_idx:
            phase = "verify"
        else:
            phase = "other"

        for k in ["input", "output", "cache_read", "cache_create"]:
            phase_tokens[phase][k] += tc[k]

    total = {
        "input":      sum(tc["input"] for tc in token_per_call),
        "output":     sum(tc["output"] for tc in token_per_call),
        "cache_read": sum(tc["cache_read"] for tc in token_per_call),
        "cache_create": sum(tc["cache_create"] for tc in token_per_call),
        "api_calls":  len(token_per_call),
    }

    phase_tool_details: dict[str, list[tuple[str, str]]] = {
        "explore": [], "implement": [], "verify": [], "other": [],
    }
    for call_i, name, detail in tool_sequence:
        if any(
            t["idx"] == call_i and any(t2 in IMPLEMENT_TOOLS for t2 in t["tools"])
            for t in token_per_call
        ):
            phase = "implement"
        elif first_edit_call_idx is None or call_i < first_edit_call_idx:
            phase = "explore"
        elif last_edit_call_idx is not None and call_i > last_edit_call_idx:
            phase = "verify"
        else:
            phase = "other"
        phase_tool_details[phase].append((name, detail))

    return {
        "agent_type":        meta.get("agentType", "unknown"),
        "description":       meta.get("description", ""),
        "tool_counts":       tool_counts,
        "phase_tokens":      phase_tokens,
        "phase_tool_details": phase_tool_details,
        "total":             total,
    }


def format_tokens(t: int) -> str:
    if t >= 1_000_000:
        return f"{t/1_000_000:.1f}M"
    if t >= 1_000:
        return f"{t/1_000:.1f}K"
    return str(t)


def render_agent_section(agent_name: str, stats: dict) -> str:
    tc = stats["tool_counts"]
    pt = stats["phase_tokens"]
    ptd = stats.get("phase_tool_details", {})
    tot = stats["total"]

    def render_tool_details(details: list[tuple[str, str]]) -> list[str]:
        return [
            f"  - {name}: {detail}" if detail else f"  - {name}"
            for name, detail in details
        ]

    lines = [f"## {agent_name} ({stats['agent_type']})"]
    if stats.get("description"):
        lines.append(f"_{stats['description']}_")
    lines.append("")

    ex = pt["explore"]
    ex_details = ptd.get("explore", [])
    lines.append("### Phase 1: Explore")
    lines.extend(render_tool_details(ex_details) if ex_details else ["  - (none)"])
    lines.append(f"- input {format_tokens(ex['input'])} / output {format_tokens(ex['output'])} / cache_read {format_tokens(ex['cache_read'])}")
    lines.append("")

    im = pt["implement"]
    im_details = ptd.get("implement", [])
    if im_details or im["output"]:
        lines.append("### Phase 2: Implement")
        lines.extend(render_tool_details(im_details) if im_details else ["  - (none)"])
        lines.append(f"- input {format_tokens(im['input'])} / output {format_tokens(im['output'])} / cache_read {format_tokens(im['cache_read'])}")
        lines.append("")

    ve = pt["verify"]
    ve_details = ptd.get("verify", [])
    if ve_details or ve["output"]:
        lines.append("### Phase 3: Verify")
        lines.extend(render_tool_details(ve_details) if ve_details else ["  - (none)"])
        lines.append(f"- input {format_tokens(ve['input'])} / output {format_tokens(ve['output'])} / cache_read {format_tokens(ve['cache_read'])}")
        lines.append("")

    lines.append("### Total")
    all_tools = ", ".join(f"{t}×{v}" for t, v in sorted(tc.items(), key=lambda x: -x[1]))
    lines.append(f"- tool calls: {all_tools}")
    lines.append(f"- input {format_tokens(tot['input'])} / output {format_tokens(tot['output'])}")
    lines.append(f"- cache_read {format_tokens(tot['cache_read'])} / cache_create {format_tokens(tot['cache_create'])}")
    lines.append(f"- API calls: {tot['api_calls']}")

    return "\n".join(lines)


def compute_efficiency(all_stats: list[dict]) -> str:
    lines = ["## Efficiency Signals"]

    impl_stat = next((s for s in all_stats if "implementer" in s["agent_type"]), None)
    if impl_stat:
        tot = impl_stat["total"]
        pt = impl_stat["phase_tokens"]
        total_all = tot["input"] + tot["output"] + tot["cache_read"]
        if total_all > 0:
            for phase_key, label in [("explore", "explore"), ("implement", "implement"), ("verify", "verify")]:
                p = pt[phase_key]
                tok = p["input"] + p["output"] + p["cache_read"]
                pct = round(tok / total_all * 100)
                lines.append(
                    f"- {label}: {format_tokens(p['input'])} in + {format_tokens(p['output'])} out"
                    f" + {format_tokens(p['cache_read'])} cache = {format_tokens(tok)} ({pct}%)"
                )
        lines.append(
            f"- implementer total: {format_tokens(tot['input'])} in"
            f" / {format_tokens(tot['output'])} out"
            f" / {format_tokens(tot['cache_read'])} cache_read"
        )

    lines.append("")
    lines.append("| agent | input | output | cache_read | cache_create | API calls |")
    lines.append("|---|---|---|---|---|---|")
    for s in all_stats:
        t = s["total"]
        lines.append(
            f"| {s['agent_type']}"
            f" | {format_tokens(t['input'])}"
            f" | {format_tokens(t['output'])}"
            f" | {format_tokens(t['cache_read'])}"
            f" | {format_tokens(t['cache_create'])}"
            f" | {t['api_calls']} |"
        )

    grand_input        = sum(s["total"]["input"] for s in all_stats)
    grand_output       = sum(s["total"]["output"] for s in all_stats)
    grand_cache_read   = sum(s["total"]["cache_read"] for s in all_stats)
    grand_cache_create = sum(s["total"]["cache_create"] for s in all_stats)
    grand_calls        = sum(s["total"]["api_calls"] for s in all_stats)
    lines.append(
        f"| **total**"
        f" | **{format_tokens(grand_input)}**"
        f" | **{format_tokens(grand_output)}**"
        f" | **{format_tokens(grand_cache_read)}**"
        f" | **{format_tokens(grand_cache_create)}**"
        f" | **{grand_calls}** |"
    )

    return "\n".join(lines)


def analyze(session_dir: Path, task_number: str, project_dir: str) -> str:
    subagents_dir = session_dir / "subagents"
    if not subagents_dir.exists():
        return f"ERROR: subagents directory not found: {subagents_dir}"

    src_prefix = str(Path(project_dir).resolve()) + "/"

    agent_files = sorted(
        [f for f in subagents_dir.iterdir() if f.suffix == ".jsonl"],
        key=lambda f: f.stat().st_mtime,
    )

    all_stats = []
    sections = []
    for jsonl_path in agent_files:
        meta_path = jsonl_path.with_suffix("").with_suffix(".meta.json")
        try:
            stats = parse_subagent(jsonl_path, meta_path, src_prefix)
            all_stats.append(stats)
            sections.append(render_agent_section(jsonl_path.stem, stats))
        except Exception as e:
            sections.append(f"## {jsonl_path.stem}\nERROR: {e}")

    efficiency = compute_efficiency(all_stats)
    return "\n\n".join(sections + [efficiency])


def update_log(log_path: Path, analysis: str) -> None:
    """Update the Phase Log / Efficiency section of a task log file."""
    if not log_path.exists():
        log_path.write_text(analysis + "\n")
        return

    content = log_path.read_text()

    marker_start = "## Planner Phase Log"
    marker_end = "## Files Changed"

    if marker_start in content and marker_end in content:
        before = content[: content.index(marker_start)]
        after = content[content.index(marker_end):]
        content = before + analysis + "\n\n" + after
    else:
        if "## Outcome" in content:
            content = content.replace("## Outcome", analysis + "\n\n## Outcome")
        else:
            content = content + "\n\n" + analysis

    log_path.write_text(content)


def main():
    parser = argparse.ArgumentParser(description="ADO workflow session log generator")
    sub = parser.add_subparsers(dest="cmd")

    p_analyze = sub.add_parser("analyze")
    p_analyze.add_argument("--session-id", default=None)
    p_analyze.add_argument("--task-number", required=True)
    p_analyze.add_argument(
        "--project-dir",
        default=str(FRONTEND_ROOT),
        help="Path to the frontend project root (default: derived from script location)",
    )
    p_analyze.add_argument("--auto-session", action="store_true")
    p_analyze.add_argument(
        "--write-log",
        action="store_true",
        help="Write result directly to .claude/logs/tasks/{taskNumber}_{date}.md",
    )

    args = parser.parse_args()

    if args.cmd == "analyze":
        session_dir = find_session_dir(
            args.project_dir,
            session_id=args.session_id,
            auto=args.auto_session,
        )
        if not session_dir:
            print("ERROR: session directory not found.", file=sys.stderr)
            sys.exit(1)

        print(f"session: {session_dir.name}", file=sys.stderr)
        result = analyze(session_dir, args.task_number, args.project_dir)

        if args.write_log:
            today = datetime.now().strftime("%Y%m%d")
            log_path = (
                Path(args.project_dir)
                / ".claude"
                / "logs"
                / "tasks"
                / f"{args.task_number}_{today}.md"
            )
            log_path.parent.mkdir(parents=True, exist_ok=True)
            update_log(log_path, result)
            print(f"Log updated: {log_path}", file=sys.stderr)
        else:
            print(result)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
