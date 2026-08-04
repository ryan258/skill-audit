#!/usr/bin/env python3
"""Routing harness: given a request, does the model pick the right skill?

The other half of skill_audit.py, deliberately kept separate. That tool is
static, offline, instant and deterministic. This one shells out to a real model
and is none of those things — a check you run and read, not a gate you trust
blindly. Keeping them apart is what keeps the auditor dependency-free.

Only POCKET skills are offered. A shelved skill is not in the model's listing,
so it cannot be routed to, and pretending otherwise would test a fiction.

Cases are JSONL: {"query": "...", "expected": "skill-name"}, or "expected": null
for "no skill should fire". Routing is a classification problem, so grading is
string equality — no second model judging prose, nothing to calibrate.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from concurrent import futures
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import skill_audit as sa

NONE = "NONE"
SYSTEM = ("You are the skill router for an agent. Given the available skills and a user request, "
          "reply with exactly one skill name from the list, or %s if no skill fits. "
          "Reply with the name only - no punctuation, no explanation." % NONE)


def pocket_listing(args: argparse.Namespace) -> List[Tuple[str, str]]:
    """The name/description pairs a model actually sees, straight from the auditor."""
    report = sa.build_report(argparse.Namespace(repo=args.repo, config=args.config, tool=args.tool))
    return sorted({(skill["name"], skill["description"]) for skill in report["skills"]
                   if "POCKET" in skill["states"].values()})


def load_cases(path: Path) -> List[Dict[str, Any]]:
    cases = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"): continue
        try:
            case = json.loads(line)
        except ValueError as exc:
            raise SystemExit("%s line %d: %s" % (path, number, exc))
        if not isinstance(case, dict) or not case.get("query"):
            raise SystemExit("%s line %d: needs a non-empty \"query\"" % (path, number))
        if "expected" not in case:
            raise SystemExit("%s line %d: needs \"expected\" (a skill name, or null for no skill)" % (path, number))
        expected = case["expected"]
        # Caught here, with a line number, rather than as an AttributeError deep
        # in grading after the model calls have already been paid for.
        if expected is not None and not (isinstance(expected, str) and expected.strip()):
            raise SystemExit("%s line %d: \"expected\" must be a skill name or null, got %r" % (path, number, expected))
        cases.append(case)
    return cases


def ask_claude(model: str, listing: str, query: str) -> str:
    prompt = "AVAILABLE SKILLS\n%s\n\nUSER REQUEST\n%s" % (listing, query)
    try:
        result = subprocess.run(["claude", "-p", "--model", model, "--system-prompt", SYSTEM, prompt],
                                capture_output=True, text=True, timeout=180)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return "ERROR: %s" % exc
    if result.returncode != 0:
        detail = result.stderr.strip().splitlines()
        return "ERROR: %s" % (detail[-1] if detail else "claude exited %d" % result.returncode)
    # A router that answers in a sentence has already failed the format, but the
    # first token is still the routing decision worth grading.
    answer = result.stdout.strip()
    return answer.splitlines()[0].strip() if answer else "ERROR: empty response"


def matches(expected: Optional[str], answer: str) -> bool:
    return answer.strip().casefold() == (expected or NONE).casefold()


def run_cases(cases: List[Dict[str, Any]], listing: List[Tuple[str, str]], model: str,
              repeat: int, jobs: int, ask: Callable[[str, str, str], str] = ask_claude) -> List[Dict[str, Any]]:
    # An expectation naming a skill outside the listing can never pass, and
    # scoring it as a routing miss is a lie about a shelved or absent skill. It
    # is skipped before the trials are built, so it costs no model calls either.
    names = {name for name, _ in listing}
    results: List[Dict[str, Any]] = [
        {"query": case["query"], "expected": case["expected"], "answers": [], "passed": 0, "rate": None,
         "skipped": bool(case["expected"]) and case["expected"] not in names}
        for case in cases]
    text = "\n".join("%s: %s" % pair for pair in listing)
    trials = [(index, case) for index, case in enumerate(cases)
              if not results[index]["skipped"] for _ in range(repeat)]
    with futures.ThreadPoolExecutor(max_workers=max(1, jobs)) as pool:
        answers = list(pool.map(lambda trial: ask(model, text, trial[1]["query"]), trials))
    for (index, _), answer in zip(trials, answers):
        results[index]["answers"].append(answer)
    for result in results:
        if result["skipped"]: continue
        result["passed"] = sum(1 for answer in result["answers"] if matches(result["expected"], answer))
        result["rate"] = result["passed"] / len(result["answers"])
    return results


def report_lines(results: List[Dict[str, Any]], listing: List[Tuple[str, str]]) -> List[str]:
    lines = ["route-check | %d skills in the pocket listing" % len(listing)]
    for result in results:
        total = len(result["answers"])
        if result["skipped"]:
            lines.append("SKIP   -/-   want %-24s %s" % (result["expected"], json.dumps(result["query"])))
            lines.append("             not in the pocket listing (shelved or not installed) — not scored")
            continue
        verdict = "PASS" if result["passed"] == total else "FAIL"
        lines.append("%s  %d/%d  want %-24s %s" % (verdict, result["passed"], total,
                                                   result["expected"] or NONE, json.dumps(result["query"])))
        wrong = sorted({answer for answer in result["answers"] if not matches(result["expected"], answer)})
        if wrong: lines.append("            got: %s" % ", ".join(wrong))
    scored = [result for result in results if not result["skipped"]]
    skipped = len(results) - len(scored)
    summary = "\n%d/%d cases passed every trial" % (sum(1 for r in scored if r["rate"] == 1), len(scored))
    lines.append(summary + ("" if not skipped else "; %d skipped (expectation not in the listing)" % skipped))
    return lines


def positive_int(value: str) -> int:
    number = int(value)
    if number < 1: raise argparse.ArgumentTypeError("must be 1 or more, got %s" % value)
    return number


def main(argv: Optional[List[str]] = None) -> int:
    arg = argparse.ArgumentParser(description=__doc__.splitlines()[0],
                                  epilog="Exit 0: every case passed every trial; 1: a case failed; 3: harness failure.")
    arg.add_argument("cases", help="JSONL file of routing cases")
    arg.add_argument("--model", default="sonnet", help="Model alias passed to `claude --model` (default: sonnet)")
    arg.add_argument("--repeat", type=positive_int, default=1, metavar="N",
                     help="Trials per case. Routing is non-deterministic; N>1 measures how reliably it holds.")
    arg.add_argument("--jobs", type=positive_int, default=8, metavar="N", help="Parallel model calls (default: 8)")
    arg.add_argument("--repo", action="append", default=[], metavar="PATH", help="Repository to scan (repeatable)")
    arg.add_argument("--config", help="TOML config path (default ~/.skill-audit.toml)")
    arg.add_argument("--tool", choices=sa.TOOLS, action="append", help="Limit the listing to a tool")
    arg.add_argument("--json", action="store_true", help="Emit results as JSON")
    args = arg.parse_args(argv)
    try:
        listing = pocket_listing(args)
        if not listing:
            print("no pocket skills found — nothing to route", file=sys.stderr); return 3
        results = run_cases(load_cases(Path(args.cases).expanduser()), listing, args.model, args.repeat, args.jobs)
        if args.json: print(json.dumps({"model": args.model, "listing_size": len(listing), "results": results}, indent=2))
        else: print("\n".join(report_lines(results, listing)))
        return 1 if any(result["rate"] is not None and result["rate"] < 1 for result in results) else 0
    except SystemExit:
        raise
    except Exception as exc:
        print("route-check failed: %s" % exc, file=sys.stderr); return 3


if __name__ == "__main__":
    raise SystemExit(main())
