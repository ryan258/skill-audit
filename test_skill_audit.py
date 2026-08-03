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


def test_multiline_plain_scalar_is_folded_not_truncated():
    """A wrapped description must survive whole; truncation poisons every check."""
    text = ("---\nname: grill-me\n"
            "description: Interview the user about a plan\n"
            "    until reaching shared understanding.\n"
            '    Use when the user wants to stress-test a plan.\n'
            "disable-model-invocation: true\n---\n")
    data, bad, ok = sa.parse_frontmatter(text)
    assert not bad, bad
    assert data["description"].endswith("stress-test a plan."), data["description"]
    assert "Use when" in data["description"], "trigger language must not be truncated away"
    assert data["disable-model-invocation"] == "true", "folding must stop at the next key"


def test_trigger_heuristic_accepts_timing_based_instructions():
    """Timing phrases are valid routing guidance, not missing triggers."""
    tmp = Path(tempfile.mkdtemp())
    try:
        skills = tmp / "repo/.claude/skills"
        write_skill(skills, "before", "---\nname: before\n"
                    "description: Prepare a story for publication. Use before publishing a story.\n---\n")
        write_skill(skills, "after", "---\nname: after\n"
                    "description: Check a release for regressions. Use after deploying a release.\n---\n")
        write_skill(skills, "end", "---\nname: end\n"
                    "description: Preserve a reusable procedure. Use at the end of a completed session.\n---\n")
        # "use as" is deliberately NOT accepted: it matches ordinary prose
        # ("a palette to use as inspiration") and would defeat the check.
        write_skill(skills, "prose", "---\nname: prose\n"
                    "description: A curated color palette to use as inspiration for mood boards.\n---\n")
        report = run(tmp)
        flagged = {item["skill"] for item in report["findings"] if item["code"] == "missing_trigger"}
        assert not {"before", "after", "end"} & flagged, flagged
        assert "prose" in flagged, flagged
    finally:
        shutil.rmtree(tmp)


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
        {"name": "dup", "real_path": "/home/dup", "scopes": ["global"],
         "precedence_keys": ["claude:global", "agents:global"], "tools": ["claude", "gemini"]},
        {"name": "dup", "real_path": "/repo/dup", "scopes": ["project"],
         "precedence_keys": ["claude:project", "agents:project"], "tools": ["claude", "gemini"]},
    ]
    claude = sa.collision_winner("claude", group)
    # Verified against code.claude.com/docs/en/skills: "enterprise overrides
    # personal, and personal overrides project". This is the opposite of Claude's
    # settings precedence; the assertion guards against someone aligning them.
    assert claude["winner"] == "/home/dup", claude   # personal beats project
    gemini = sa.collision_winner("gemini", group)
    assert gemini["winner"] == "/repo/dup", gemini   # workspace beats user
    codex = sa.collision_winner("codex", group)
    assert codex["winner"] is None and len(codex["tied"]) == 2, codex


def test_gemini_agents_path_beats_gemini_path_within_a_tier():
    """.agents/skills is the cross-agent standard; .gemini/skills is the alias."""
    same_tier = [
        {"name": "dup", "real_path": "/home/gemini/dup", "scopes": ["global"],
         "precedence_keys": ["gemini:global"], "tools": ["gemini"]},
        {"name": "dup", "real_path": "/home/agents/dup", "scopes": ["global"],
         "precedence_keys": ["agents:global"], "tools": ["gemini"]},
    ]
    result = sa.collision_winner("gemini", same_tier)
    assert result["winner"] == "/home/agents/dup", result
    assert result["tier"] == "user", result

    project = [
        {"name": "dup", "real_path": "/repo/gemini/dup", "scopes": ["project"],
         "precedence_keys": ["gemini:project"], "tools": ["gemini"]},
        {"name": "dup", "real_path": "/repo/agents/dup", "scopes": ["project"],
         "precedence_keys": ["agents:project"], "tools": ["gemini"]},
    ]
    assert sa.collision_winner("gemini", project)["winner"] == "/repo/agents/dup"

    # And a workspace copy still beats any user copy, whichever family it is in.
    across = [same_tier[1], project[0]]
    assert sa.collision_winner("gemini", across)["winner"] == "/repo/gemini/dup"


def test_path_family_identifies_the_cupboard():
    assert sa.path_family(Path("/Users/x/.agents/skills")) == "agents"
    assert sa.path_family(Path("/Users/x/.gemini/skills")) == "gemini"
    assert sa.path_family(Path("/Users/x/.gemini/config/skills")) == "gemini"
    assert sa.path_family(Path("/Users/x/.claude/skills")) == "claude"
    assert sa.path_family(Path("/repo/.agents/skills")) == "agents"
    # Nearest marker wins: a repo living under ~/.agents or ~/.gemini must not
    # drag its own .claude/skills into the wrong family, which would make a real
    # collision report "precedence not determinable".
    assert sa.path_family(Path("/Users/x/.agents/myrepo/.claude/skills")) == "claude"
    assert sa.path_family(Path("/Users/x/.gemini/ext/e/.claude/skills")) == "claude"
    assert sa.path_family(Path("/Users/x/.claude/plugins/p/.agents/skills")) == "agents"
    assert sa.path_family(Path("/repo/no/markers/here")) == "other"


def test_unmatched_precedence_key_returns_undeterminable():
    group = [
        {"name": "dup", "real_path": "/home/dup", "scopes": ["global"],
         "precedence_keys": ["other:global"], "tools": ["claude"]},
        {"name": "dup", "real_path": "/repo/dup", "scopes": ["project"],
         "precedence_keys": ["claude:project"], "tools": ["claude"]},
    ]
    claude = sa.collision_winner("claude", group)
    assert claude["winner"] is None, claude
    assert claude["note"] == "unrecognized skill root — precedence not determinable", claude


def test_nested_gemini_skills_discovered_and_ranked():
    tmp = Path(tempfile.mkdtemp())
    try:
        sub_gemini = tmp / "repo/sub/.gemini/skills"
        write_skill(sub_gemini, "nested-gem", "---\nname: nested-gem\ndescription: Formats a script. Use when the user asks to format.\n---\n")
        roots = list(sa.project_roots(tmp / "repo"))
        found = [(p, tool, nested) for p, tool, nested in roots if "sub/.gemini/skills" in str(p)]
        assert len(found) == 1, roots
        p, tool, nested = found[0]
        assert tool == "gemini" and nested is True
        records, _ = sa.scan_root(p, tool, "nested", nested=nested)
        assert records[0]["precedence_key"] == "gemini:nested"
    finally:
        shutil.rmtree(tmp)


def test_anchors_and_tags_are_flagged_not_stored():
    for value in ("&ref value", "*alias", "!!str thing", "@reserved"):
        assert sa.parse_scalar(value)[0] is False, value
    assert sa.parse_scalar("plain value")[0] is True


def test_findings_name_the_skill_when_there_is_no_path():
    report = {"meta": {"version": "t", "paths_verified": "d", "locations_scanned": [],
                       "config": "c", "config_present": False},
              "skills": [], "collisions": [], "overlaps": [],
              "budget": {"claude": {"total": 0, "limit": 1, "status": "pass", "pocket_skills": 0},
                         "codex": {"total": 0, "limit": 1, "status": "pass", "pocket_skills": 0},
                         "excluded_unknown": 0},
              "pocket_check": {"rule": "r", "pocket_count": 0, "correct": [],
                               "intended_shelf_but_pocket": [], "intended_pocket_but_shelf": []},
              "recommendations": [],
              "findings": [sa.finding("warning", "intended_shelf_pocket", "Intended shelf skill is actually pocket", "grill-me")]}
    text = "\n".join(sa.lines_for(report))
    assert "grill-me" in text, "a finding with no path must still name its skill"


def test_recommendations_keep_distinct_skills_apart():
    findings = [sa.finding("error", "missing_description", "Missing or unreadable description", "alpha", "/a"),
                sa.finding("error", "missing_description", "Missing or unreadable description", "bravo", "/b")]
    lines = sa.recommendations_for(findings)
    assert len(lines) == 1, "same issue groups into one line"
    assert "alpha" in lines[0] and "bravo" in lines[0], lines
    assert "2 affected" in lines[0], lines


def test_scan_findings_dedupe_by_real_path():
    tmp = Path(tempfile.mkdtemp())
    try:
        (tmp / "source").mkdir()
        (tmp / "source/dead").symlink_to(tmp / "nowhere")
        (tmp / "cupA").symlink_to(tmp / "source")
        (tmp / "cupB").symlink_to(tmp / "source")
        findings = [sa.finding("warning", "broken_symlink", "Broken symlink", path=str(tmp / "cupA/dead")),
                    sa.finding("warning", "broken_symlink", "Broken symlink", path=str(tmp / "cupB/dead"))]
        assert len(sa.dedupe_scan_findings(findings)) == 1, "one dead link, reachable twice, is one problem"
    finally:
        shutil.rmtree(tmp)


def test_overlap_labels_disambiguate_two_copies_of_one_name():
    shared = "alpha bravo charlie delta echo foxtrot"
    pair = [{"name": "dup", "real_path": "/home/dup", "description": shared},
            {"name": "dup", "real_path": "/repo/dup", "description": shared}]
    overlaps = sa.overlap_report(pair, {}, [])
    assert overlaps[0]["labels"] == ["/home/dup", "/repo/dup"], overlaps[0]["labels"]


def test_project_skills_are_not_measured_against_the_global_config():
    skills = [{"name": "global-one", "scopes": ["global"], "states": {"claude": "POCKET"}},
              {"name": "repo-one", "scopes": ["nested"], "states": {"claude": "POCKET"}}]
    result = sa.pocket_report(skills, {"pocket": {"skills": ["global-one"]}}, [])
    assert result["correct"] == ["global-one"], result
    assert result["intended_shelf_but_pocket"] == [], "a repo skill is not global drift"
    assert result["project_pocket"] == ["repo-one"], result
    assert result["pocket_count"] == 2, "still counted, just not compared"


def test_duplicate_names_union_their_scopes():
    """A name that is global in one copy stays subject to the global config."""
    skills = [{"name": "dup", "scopes": ["nested"], "states": {"claude": "POCKET"}},
              {"name": "dup", "scopes": ["global"], "states": {"claude": "POCKET"}}]
    result = sa.pocket_report(skills, {"pocket": {"skills": ["other"]}}, [])
    assert result["project_pocket"] == [], "the global copy must not be lost to dict overwrite"
    assert result["intended_shelf_but_pocket"] == ["dup"], result


def test_quiet_names_what_it_suppressed():
    tmp = Path(tempfile.mkdtemp())
    try:
        (tmp / "repo/.claude/skills").mkdir(parents=True)
        write_skill(tmp / "repo/.claude/skills", "solo",
                    "---\nname: solo\ndescription: Formats a script. Use when the user asks to format.\n---\n")
        text = "\n".join(sa.lines_for(run(tmp), quiet=True))
        assert "suppressed by --quiet" in text, "a section must never vanish without saying so"
    finally:
        shutil.rmtree(tmp)


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
        # The section headers are gone, but the suppression is announced.
        assert not any(line == "\nInventory" for line in quiet)
        assert not any(line == "\nBudget" for line in quiet)
        assert any("suppressed by --quiet" in line for line in quiet)
        assert any(line == "\nInventory" for line in loud)
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
