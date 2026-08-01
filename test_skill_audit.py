#!/usr/bin/env python3
"""Self-check for skill_audit. Run: python3 test_skill_audit.py

No framework. Builds throwaway skill trees in a temp dir and asserts on the
report. Covers the acceptance criteria in brief.md section 10 that are
verifiable without a real agent install.
"""
import argparse
import json
import shutil
import tempfile
from pathlib import Path

import skill_audit as sa

REFERENCE = """---
name: example-skill
description: "Reviews a draft for voice. Use when the user asks for a voice check."
allowed-tools: [Read, Grep]
disable-model-invocation: true
paths:
  - src/**/*.ts
  - docs/*.md
when_to_use: |
  Trigger on "check my voice" or "does this sound like me".
  Do not trigger on general editing requests.
---
body
"""


def test_parses_all_five_yaml_forms():
    data, bad, ok = sa.parse_frontmatter(REFERENCE)
    assert ok and not bad, bad
    assert data["name"] == "example-skill"
    assert data["allowed-tools"] == ["Read", "Grep"]                  # flow list
    assert data["disable-model-invocation"] == "true"                 # bare scalar
    assert data["paths"] == ["src/**/*.ts", "docs/*.md"]              # block list
    assert data["when_to_use"].startswith("Trigger on")               # block scalar
    assert "\n" in data["when_to_use"], "literal block keeps newlines"


def test_flags_a_sixth_unsupported_form():
    data, bad, ok = sa.parse_frontmatter("---\nname: x\nmapping: {a: 1}\n---\n")
    assert ok and bad, "inline flow mapping must be flagged, not guessed"
    assert bad[0][0] == "mapping" and bad[0][1] == 3, bad


def test_plain_scalar_colon_rejected_but_hash_allowed():
    assert sa.parse_scalar("Does a thing: then another")[0] is False
    assert sa.parse_scalar("Refactors C# code")[0] is True, "bare # is legal YAML"
    assert sa.parse_scalar("trailing value # comment")[0] is False


def test_no_frontmatter_is_detected():
    data, bad, ok = sa.parse_frontmatter("# Just markdown\n")
    assert ok is False and data is None


def test_codex_policy_with_sibling_interface_block():
    text = ('interface:\n  display_name: "Grill Me"\n'
            'policy:\n  allow_implicit_invocation: false\n')
    data, bad, ok = sa.parse_frontmatter("---\n" + text + "---\n", nested_policy=True)
    assert not bad, "a sibling mapping must not produce spurious findings: %s" % bad
    assert data["policy"]["allow_implicit_invocation"] == "false"
    assert sa.bool_value(data["policy"]["allow_implicit_invocation"]) is False


def test_overlap_thresholds():
    assert len(sa.description_tokens("alpha bravo charlie delta echo") &
               sa.description_tokens("alpha bravo charlie delta echo")) >= 5
    findings = []
    five = {"name": "a", "description": "alpha bravo charlie delta echo"}
    also = {"name": "b", "description": "alpha bravo charlie delta echo"}
    pairs = sa.overlap_report([five, also], {}, findings)
    assert pairs and pairs[0]["severity"] == "warning", pairs

    findings = []
    two = {"name": "c", "description": "alpha bravo zulu"}
    other = {"name": "d", "description": "alpha bravo yankee"}
    assert sa.overlap_report([two, other], {}, findings) == [], "2 shared terms must be silent"


def test_budget_ignores_unknown_from_other_tools():
    skills = [
        {"name": "seen", "description": "d" * 100, "states": {"claude": "POCKET", "gemini": "UNKNOWN"},
         "real_path": "/x"},
        {"name": "gemonly", "description": "d" * 100, "states": {"gemini": "UNKNOWN"}, "real_path": "/y"},
    ]
    budget = sa.budget_report(skills, {}, [])
    assert budget["claude"]["pocket_skills"] == 1, budget
    assert budget["claude"]["total"] == len("seen") + 100, budget
    # Only the Gemini-only skill is truly excluded; the Claude-visible one is counted.
    assert budget["excluded_unknown"] == 1, budget


def test_budget_is_per_tool_not_per_skill():
    """A skill shelved in Claude but pocket in Codex costs Codex only."""
    mixed = {"name": "mixed", "description": "d" * 100, "real_path": "/m",
             "states": {"claude": "SHELF", "codex": "POCKET"}}
    budget = sa.budget_report([mixed], {}, [])
    assert budget["claude"]["total"] == 0 and budget["claude"]["pocket_skills"] == 0, budget
    assert budget["codex"]["total"] == len("mixed") + 100, budget
    assert budget["codex"]["pocket_skills"] == 1, budget

    # And the mirror case, so neither tool is special-cased by accident.
    flipped = dict(mixed, states={"claude": "POCKET", "codex": "SHELF"})
    budget = sa.budget_report([flipped], {}, [])
    assert budget["codex"]["total"] == 0, budget
    assert budget["claude"]["total"] == len("mixed") + 100, budget


def test_collision_winner_prefers_documented_tier():
    group = [
        {"name": "dup", "real_path": "/home/dup", "scopes": ["global"], "tools": ["claude", "gemini"]},
        {"name": "dup", "real_path": "/repo/dup", "scopes": ["project"], "tools": ["claude", "gemini"]},
    ]
    claude = sa.collision_winner("claude", group)
    assert claude["winner"] == "/home/dup", claude   # personal beats project
    gemini = sa.collision_winner("gemini", group)
    assert gemini["winner"] == "/repo/dup", gemini   # workspace beats user
    codex = sa.collision_winner("codex", group)
    assert codex["winner"] is None and len(codex["tied"]) == 2, codex


def write_skill(root: Path, name: str, body: str) -> Path:
    path = root / name
    path.mkdir(parents=True)
    (path / "SKILL.md").write_text(body, encoding="utf-8")
    return path


def run(tmp: Path, **overrides) -> dict:
    """Build a report against tmp only — never the real home directory."""
    args = argparse.Namespace(repo=[str(tmp / "repo")], config=str(tmp / "missing.toml"),
                              json=False, markdown=None, quiet=False, tool=["claude"],
                              strict=False, version=False)
    for key, value in overrides.items():
        setattr(args, key, value)
    real_globals, real_antigravity = sa.GLOBAL_PATHS, sa.ANTIGRAVITY_NON_PORTABLE
    sa.GLOBAL_PATHS = {tool: (str(tmp / "global" / tool),) for tool in sa.TOOLS}
    sa.ANTIGRAVITY_NON_PORTABLE = (str(tmp / "global/nonportable"),)
    try:
        return sa.build_report(args)
    finally:
        sa.GLOBAL_PATHS, sa.ANTIGRAVITY_NON_PORTABLE = real_globals, real_antigravity


def test_end_to_end_on_a_temp_repo():
    tmp = Path(tempfile.mkdtemp())
    try:
        skills = tmp / "repo/.claude/skills"
        skills.mkdir(parents=True)
        write_skill(skills, "shelved", "---\nname: shelved\n"
                    "description: Audits a draft for tone. Use when the user asks for a tone pass.\n"
                    "disable-model-invocation: true\n---\nbody\n")
        write_skill(skills, "bare", "no frontmatter here\n")
        (skills / "dangling").symlink_to(tmp / "nowhere")

        report = run(tmp)
        by_name = {s["name"]: s for s in report["skills"]}
        codes = {f["code"] for f in report["findings"]}

        assert by_name["shelved"]["states"]["claude"] == "SHELF", by_name["shelved"]
        assert "no_frontmatter" in codes, codes
        assert "broken_symlink" in codes, "a dangling link must not stop the scan"
        assert "bare" in by_name, "scan continued past the broken pieces"

        # Every finding carries a stable, registered code and a valid severity.
        for item in report["findings"]:
            assert item["code"] in sa.FINDING_CODES, item
            assert item["severity"] in ("error", "warning", "notice"), item
        assert json.dumps(report), "report must be JSON-serialisable"
        for key in ("meta", "skills", "findings", "collisions", "overlaps",
                    "budget", "pocket_check", "recommendations"):
            assert key in report, key
    finally:
        shutil.rmtree(tmp)


def test_quiet_keeps_collisions_and_changes_no_exit_code():
    tmp = Path(tempfile.mkdtemp())
    try:
        (tmp / "repo/.claude/skills").mkdir(parents=True)
        write_skill(tmp / "repo/.claude/skills", "solo",
                    "---\nname: solo\ndescription: Formats a script. Use when the user asks to format.\n---\n")
        report = run(tmp)
        loud = sa.lines_for(report, quiet=False)
        quiet = sa.lines_for(report, quiet=True)
        assert any("Name collisions" in line for line in quiet), "brief 8b: quiet skips inventory/budget/pocket only"
        assert any("Overlap candidates" in line for line in quiet)
        assert not any("Inventory" in line for line in quiet)
        assert not any("Budget" in line for line in quiet)
        assert any("Inventory" in line for line in loud)
    finally:
        shutil.rmtree(tmp)


def test_empty_machine_does_not_crash():
    tmp = Path(tempfile.mkdtemp())
    try:
        (tmp / "repo").mkdir()
        report = run(tmp)
        assert report["skills"] == []
        assert sa.lines_for(report), "sections still print on an empty machine"
    finally:
        shutil.rmtree(tmp)


if __name__ == "__main__":
    tests = [value for key, value in sorted(globals().items()) if key.startswith("test_")]
    for test in tests:
        test()
        print("ok  %s" % test.__name__)
    print("\n%d passed" % len(tests))
