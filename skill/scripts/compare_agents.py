#!/usr/bin/env python3
"""Harvest subagent-comparison metrics from a Claude Code session transcript.

jetmemo's comparison mode (see references/model-comparison.md) dispatches the
same agent prompt to two or three arms — Opus, a second Opus control, and
Sonnet — labelling each `Agent` call with a description of the form:

    cmp <slot> <arm>          e.g. "cmp A opus", "cmp A opus2", "cmp D sonnet"

Claude Code records every completed Agent call in the session's JSONL
transcript, including `resolvedModel`, `totalDurationMs`, `totalTokens`, the
full `usage` breakdown, and `toolStats`. This script reads those records, pairs
them by slot, and emits an objective metrics table. Nothing needs to be
instrumented inside the subagents.

Usage:
    python3 compare_agents.py                       # newest transcript for $PWD
    python3 compare_agents.py --transcript FILE.jsonl
    python3 compare_agents.py --json
    python3 compare_agents.py --out comparison.md

Exit codes:
    0  metrics found and reported
    1  no comparison-tagged agent runs found
    2  transcript could not be located
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

__version__ = "1.0.0"

# Description tag written by the orchestrator on each Agent call.
TAG_RE = re.compile(r"^cmp[\s:_-]+(?P<slot>[A-Za-z0-9]+)[\s:_-]+(?P<arm>[A-Za-z0-9]+)$")

# Per-million-token prices, keyed by the model ID with any context-window
# suffix (e.g. "[1m]") stripped. Update when Anthropic pricing changes.
#
# Sourced 2026-08-03. Sonnet 5's introductory rate ($2/$10) runs through
# 2026-08-31; SONNET_INTRO_UNTIL below switches to the standard $3/$15 after
# that date so a later run does not silently under-report cost.
PRICING = {
    "claude-opus-5": (5.00, 25.00),
    "claude-opus-4-8": (5.00, 25.00),
    "claude-opus-4-7": (5.00, 25.00),
    "claude-opus-4-6": (5.00, 25.00),
    "claude-sonnet-5": (2.00, 10.00),  # intro rate; see SONNET_INTRO_UNTIL
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-haiku-4-5": (1.00, 5.00),
    "claude-fable-5": (10.00, 50.00),
}
SONNET_INTRO_UNTIL = "2026-08-31"
SONNET_STANDARD = (3.00, 15.00)

# Cache-write multipliers over the base input rate, by TTL.
CACHE_WRITE_5M = 1.25
CACHE_WRITE_1H = 2.00
CACHE_READ = 0.10

ARM_ORDER = ["opus", "opus2", "sonnet", "haiku", "fable"]


def project_dir_for(cwd: str) -> Path:
    """Map a working directory to its ~/.claude/projects/ transcript folder."""
    slug = re.sub(r"[^A-Za-z0-9]", "-", cwd)
    return Path.home() / ".claude" / "projects" / slug


def newest_transcript(cwd: str) -> Path | None:
    d = project_dir_for(cwd)
    if not d.is_dir():
        return None
    files = sorted(d.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def base_model(resolved: str | None) -> str:
    """Strip a context-window suffix: 'claude-opus-5[1m]' -> 'claude-opus-5'."""
    if not resolved:
        return "unknown"
    return re.sub(r"\[[^\]]*\]$", "", resolved).strip()


def rates(model: str, run_date: str | None) -> tuple[float, float] | None:
    if model not in PRICING:
        return None
    if model == "claude-sonnet-5" and run_date and run_date > SONNET_INTRO_UNTIL:
        return SONNET_STANDARD
    return PRICING[model]


def cost_usd(usage: dict, model: str, run_date: str | None) -> float | None:
    """Price one agent run from its usage breakdown, or None if unpriced."""
    r = rates(model, run_date)
    if r is None:
        return None
    in_rate, out_rate = r

    creation = usage.get("cache_creation") or {}
    write_1h = creation.get("ephemeral_1h_input_tokens", 0) or 0
    write_5m = creation.get("ephemeral_5m_input_tokens", 0) or 0
    if not (write_1h or write_5m):
        # Older records only carry the flat total; assume the 5-minute rate.
        write_5m = usage.get("cache_creation_input_tokens", 0) or 0

    billable_in = (
        (usage.get("input_tokens", 0) or 0)
        + CACHE_WRITE_1H * write_1h
        + CACHE_WRITE_5M * write_5m
        + CACHE_READ * (usage.get("cache_read_input_tokens", 0) or 0)
    )
    out = usage.get("output_tokens", 0) or 0
    return billable_in * in_rate / 1e6 + out * out_rate / 1e6


def load_runs(path: Path) -> list[dict]:
    """Return one record per comparison-tagged Agent call in the transcript."""
    descriptions: dict[str, str] = {}  # tool_use_id -> description
    results: list[dict] = []

    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue

            if rec.get("type") == "assistant":
                for block in rec.get("message", {}).get("content", []) or []:
                    if (
                        isinstance(block, dict)
                        and block.get("type") == "tool_use"
                        and block.get("name") in ("Agent", "Task")
                    ):
                        desc = (block.get("input") or {}).get("description")
                        if desc:
                            descriptions[block["id"]] = desc
                continue

            tr = rec.get("toolUseResult")
            if not isinstance(tr, dict) or "totalDurationMs" not in tr:
                continue

            tool_use_id = None
            for block in rec.get("message", {}).get("content", []) or []:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    tool_use_id = block.get("tool_use_id")
                    break
            if tool_use_id is None:
                continue

            desc = descriptions.get(tool_use_id, "")
            m = TAG_RE.match(desc.strip())
            if not m:
                continue

            usage = tr.get("usage") or {}
            model = base_model(tr.get("resolvedModel"))
            run_date = (rec.get("timestamp") or "")[:10] or None
            stats = tr.get("toolStats") or {}

            results.append(
                {
                    "slot": m.group("slot").upper(),
                    "arm": m.group("arm").lower(),
                    "description": desc,
                    "model": model,
                    "resolved_model": tr.get("resolvedModel"),
                    "status": tr.get("status"),
                    "agent_id": tr.get("agentId"),
                    "duration_s": round((tr.get("totalDurationMs") or 0) / 1000, 1),
                    "total_tokens": tr.get("totalTokens") or 0,
                    "output_tokens": usage.get("output_tokens", 0) or 0,
                    "input_tokens": usage.get("input_tokens", 0) or 0,
                    "cache_read": usage.get("cache_read_input_tokens", 0) or 0,
                    "cache_write": usage.get("cache_creation_input_tokens", 0) or 0,
                    "tool_calls": tr.get("totalToolUseCount") or 0,
                    "reads": stats.get("readCount", 0),
                    "searches": stats.get("searchCount", 0),
                    "bash": stats.get("bashCount", 0),
                    "cost_usd": cost_usd(usage, model, run_date),
                    "timestamp": rec.get("timestamp"),
                }
            )

    return results


def arm_sort_key(arm: str) -> tuple[int, str]:
    return (ARM_ORDER.index(arm) if arm in ARM_ORDER else len(ARM_ORDER), arm)


def fmt_cost(c: float | None) -> str:
    return f"${c:.4f}" if c is not None else "n/a"


def pct_delta(new: float, base: float) -> str:
    """Signed percentage change of `new` relative to `base`."""
    if not base:
        return "n/a"
    return f"{(new - base) / base * 100:+.0f}%"


def render(runs: list[dict], transcript: Path) -> str:
    slots: dict[str, list[dict]] = {}
    for r in runs:
        slots.setdefault(r["slot"], []).append(r)

    out: list[str] = []
    out.append("# Subagent Model Comparison — Metrics")
    out.append("")
    out.append(f"Transcript: `{transcript}`")
    out.append(f"Agent runs harvested: {len(runs)} across {len(slots)} slot(s)")
    out.append("")

    unpriced = sorted({r["model"] for r in runs if r["cost_usd"] is None})
    if unpriced:
        out.append(
            "> Cost unavailable for: " + ", ".join(unpriced) + " (not in the "
            "script's pricing table — update `PRICING` in compare_agents.py)."
        )
        out.append("")

    for slot in sorted(slots):
        arms = sorted(slots[slot], key=lambda r: arm_sort_key(r["arm"]))
        out.append(f"## Slot {slot}")
        out.append("")
        out.append(
            "| Arm | Resolved model | Duration | Total tokens | Output tokens "
            "| Cache read | Tool calls | Cost |"
        )
        out.append("| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |")
        for r in arms:
            out.append(
                f"| {r['arm']} | `{r['resolved_model']}` | {r['duration_s']}s "
                f"| {r['total_tokens']:,} | {r['output_tokens']:,} "
                f"| {r['cache_read']:,} | {r['tool_calls']} "
                f"| {fmt_cost(r['cost_usd'])} |"
            )
        out.append("")

        by_arm = {r["arm"]: r for r in arms}
        opus, opus2, sonnet = (
            by_arm.get("opus"),
            by_arm.get("opus2"),
            by_arm.get("sonnet"),
        )
        if opus and sonnet:
            out.append(
                f"- Sonnet vs Opus: time {pct_delta(sonnet['duration_s'], opus['duration_s'])}, "
                f"tokens {pct_delta(sonnet['total_tokens'], opus['total_tokens'])}"
                + (
                    f", cost {pct_delta(sonnet['cost_usd'], opus['cost_usd'])}"
                    if sonnet["cost_usd"] is not None and opus["cost_usd"]
                    else ""
                )
            )
        if opus and opus2:
            out.append(
                f"- **Noise floor** (Opus₂ vs Opus, same model): time "
                f"{pct_delta(opus2['duration_s'], opus['duration_s'])}, tokens "
                f"{pct_delta(opus2['total_tokens'], opus['total_tokens'])} — "
                "an Opus–Sonnet gap no larger than this is not evidence of anything."
            )
        elif opus and sonnet:
            out.append(
                "- **No control arm ran for this slot** — there is no noise "
                "floor to compare the Opus–Sonnet gap against."
            )
        out.append("")

    # Arm totals across every slot.
    totals: dict[str, dict[str, float]] = {}
    for r in runs:
        t = totals.setdefault(
            r["arm"], {"n": 0, "duration_s": 0.0, "total_tokens": 0, "cost": 0.0, "priced": 0}
        )
        t["n"] += 1
        t["duration_s"] += r["duration_s"]
        t["total_tokens"] += r["total_tokens"]
        if r["cost_usd"] is not None:
            t["cost"] += r["cost_usd"]
            t["priced"] += 1

    out.append("## Totals by arm")
    out.append("")
    out.append("| Arm | Runs | Total time | Total tokens | Total cost |")
    out.append("| --- | ---: | ---: | ---: | ---: |")
    for arm in sorted(totals, key=arm_sort_key):
        t = totals[arm]
        cost = (
            f"${t['cost']:.4f}" + ("" if t["priced"] == t["n"] else " (partial)")
            if t["priced"]
            else "n/a"
        )
        out.append(
            f"| {arm} | {int(t['n'])} | {t['duration_s']:.1f}s "
            f"| {int(t['total_tokens']):,} | {cost} |"
        )
    out.append("")

    mismatches = [
        r
        for r in runs
        if (r["arm"].startswith("opus") and "opus" not in r["model"])
        or (r["arm"] == "sonnet" and "sonnet" not in r["model"])
    ]
    if mismatches:
        out.append("## Arm/model mismatches")
        out.append("")
        out.append(
            "The model override did not take effect for these runs; their "
            "numbers are not a valid comparison:"
        )
        for r in mismatches:
            out.append(f"- `{r['description']}` resolved to `{r['resolved_model']}`")
        out.append("")

    failed = [r for r in runs if r.get("status") and r["status"] != "completed"]
    if failed:
        out.append("## Incomplete runs")
        out.append("")
        for r in failed:
            out.append(f"- `{r['description']}` — status `{r['status']}`")
        out.append("")

    out.append(
        "Timing reflects wall clock under whatever concurrency the run used; "
        "arms dispatched together face comparable load, arms dispatched at "
        "different times do not."
    )
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--transcript", help="path to a session .jsonl transcript")
    ap.add_argument(
        "--cwd",
        default=os.getcwd(),
        help="working directory whose project transcripts to search (default: cwd)",
    )
    ap.add_argument("--json", action="store_true", help="emit raw records as JSON")
    ap.add_argument("--out", help="also write the markdown report to this path")
    ap.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    args = ap.parse_args()

    if args.transcript:
        path = Path(args.transcript).expanduser()
        if not path.is_file():
            print(f"ERROR: transcript not found: {path}", file=sys.stderr)
            return 2
    else:
        found = newest_transcript(args.cwd)
        if found is None:
            print(
                f"ERROR: no transcript found for {args.cwd} "
                f"(looked in {project_dir_for(args.cwd)}). Pass --transcript.",
                file=sys.stderr,
            )
            return 2
        path = found

    runs = load_runs(path)
    if not runs:
        print(
            f"No comparison-tagged agent runs found in {path}.\n"
            "Agent calls must use a description of the form 'cmp <slot> <arm>' "
            "(e.g. 'cmp A opus').",
            file=sys.stderr,
        )
        return 1

    if args.json:
        print(json.dumps(runs, indent=2))
    else:
        report = render(runs, path)
        print(report)
        if args.out:
            Path(args.out).expanduser().write_text(report + "\n", encoding="utf-8")
            print(f"\nWrote {args.out}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
