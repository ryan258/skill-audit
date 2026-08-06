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


def test_portable_metadata_mapping_is_parsed_as_strings():
    text = ('---\nname: portable-skill\n'
            'description: "Reviews a portable skill. Use when the user asks for validation."\n'
            'metadata:\n  author: Ryan\n  version: "1"\n---\nbody\n')
    data, bad, ok = sa.parse_frontmatter(text)
    assert ok and not bad, bad
    assert data["metadata"] == {"author": "Ryan", "version": "1"}, data["metadata"]


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


def test_overlap_demoted_when_shelved():
    findings = []
    five_shelved = {"name": "a", "description": "alpha bravo charlie delta echo", "states": {"claude": "SHELF", "codex": "SHELF"}}
    five_pocket = {"name": "b", "description": "alpha bravo charlie delta echo", "states": {"claude": "POCKET", "codex": "POCKET"}}
    pairs = sa.overlap_report([five_shelved, five_pocket], {}, findings)
    assert pairs and pairs[0]["severity"] == "notice", pairs
    assert findings[0]["severity"] == "notice"


def test_reciprocal_named_boundary_keeps_overlap_visible_but_non_blocking():
    findings = []
    first = {"name": "idea-check", "real_path": "/x/idea-check",
             "description": ("Alpha bravo charlie delta echo. Use when testing an idea. "
                             "Do not use for project structure; hand that to project-build."),
             "states": {"claude": "POCKET"}}
    second = {"name": "project-build", "real_path": "/x/project-build",
              "description": ("Alpha bravo charlie delta echo. Use when structuring a project. "
                              "Do not use for idea testing; hand that to idea-check."),
              "states": {"claude": "POCKET"}}
    pairs = sa.overlap_report([first, second], {}, findings)
    assert pairs[0]["reciprocal_boundary"] is True, pairs[0]
    assert pairs[0]["severity"] == "notice", pairs[0]
    assert findings[0]["severity"] == "notice", findings



def test_budget_ignores_unknown_from_other_tools():
    skills = [
        {"name": "seen", "description": "d" * 100, "states": {"claude": "POCKET", "antigravity": "UNKNOWN"},
         "real_path": "/x"},
        {"name": "ag-only", "description": "d" * 100, "states": {"antigravity": "UNKNOWN"}, "real_path": "/y"},
    ]
    budget = sa.budget_report(skills, {}, [])
    assert budget["claude"]["pocket_skills"] == 1, budget
    assert budget["claude"]["total"] == len("seen") + 100, budget
    # Only the Antigravity-only skill is excluded; the Claude-visible one is counted.
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


def test_gemini_budget_is_counted_without_an_invented_limit():
    skill = {"name": "gem", "description": "d" * 100, "real_path": "/g",
             "states": {"gemini": "POCKET"}}
    budget = sa.budget_report([skill], {}, [])
    assert budget["gemini"]["total"] == len("gem") + 100, budget
    assert budget["gemini"]["pocket_skills"] == 1, budget
    assert budget["gemini"]["limit"] is None and budget["gemini"]["status"] == "not measured"


def test_collision_winner_prefers_documented_tier():
    group = [
        {"name": "dup", "real_path": "/home/dup", "scopes": ["global"],
         "precedence_keys": ["claude:global", "agents:global"], "tools": ["claude", "gemini", "codex"]},
        {"name": "dup", "real_path": "/repo/dup", "scopes": ["project"],
         "precedence_keys": ["claude:project", "agents:project"], "tools": ["claude", "gemini", "codex"]},
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


def test_disabled_collision_copy_does_not_compete_or_win():
    group = [
        {"name": "dup", "real_path": "/disabled", "precedence_keys": ["claude:global"],
         "tools": ["claude", "codex"], "states": {"claude": "DISABLED", "codex": "DISABLED"}},
        {"name": "dup", "real_path": "/active", "precedence_keys": ["claude:project"],
         "tools": ["claude", "codex"], "states": {"claude": "POCKET", "codex": "POCKET"}},
    ]
    assert sa.collision_winner("claude", group)["winner"] == "/active"
    codex = sa.collision_winner("codex", group)
    assert codex["winner"] == "/active" and codex["tier"] == "only enabled copy", codex


def test_collision_with_no_host_exposing_both_is_non_blocking_evidence():
    group = [
        {"name": "dup", "real_path": "/disabled", "scopes": ["global"],
         "precedence_keys": ["claude:global"], "tools": ["claude"],
         "states": {"claude": "DISABLED"}, "library": "local"},
        {"name": "dup", "real_path": "/active", "scopes": ["project"],
         "precedence_keys": ["claude:project"], "tools": ["claude"],
         "states": {"claude": "POCKET"}, "library": "local"},
    ]
    findings = []
    collisions = sa.collision_report(group, findings)
    assert collisions[0]["active_tools"] == [], collisions[0]
    assert findings[0]["severity"] == "notice", findings


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
                         "gemini": {"total": 0, "limit": None, "status": "not measured", "pocket_skills": 0},
                         sa.DESKTOP: {"total": 0, "limit": None, "status": "not measured", "pocket_skills": 0},
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


def test_distinct_dead_links_to_one_target_stay_distinct():
    """The mirror of the test above: two links, one absent target, two cleanups."""
    tmp = Path(tempfile.mkdtemp())
    try:
        (tmp / "first").symlink_to(tmp / "nowhere")
        (tmp / "second").symlink_to(tmp / "nowhere")
        findings = [sa.finding("warning", "broken_symlink", "Broken symlink", path=str(tmp / "first")),
                    sa.finding("warning", "broken_symlink", "Broken symlink", path=str(tmp / "second"))]
        kept = {item["path"] for item in sa.dedupe_scan_findings(findings)}
        assert kept == {str(tmp / "first"), str(tmp / "second")}, kept
    finally:
        shutil.rmtree(tmp)


def test_overlap_labels_disambiguate_two_copies_of_one_name():
    shared = "alpha bravo charlie delta echo foxtrot"
    pair = [{"name": "dup", "real_path": "/home/dup", "description": shared},
            {"name": "dup", "real_path": "/repo/dup", "description": shared}]
    overlaps = sa.overlap_report(pair, {}, [])
    assert overlaps[0]["labels"] == ["/home/dup", "/repo/dup"], overlaps[0]["labels"]


def test_yaml_comments_are_not_unparseable_fields():
    # A hand-written agents/openai.yaml normally explains why a skill is
    # shelved. Those comment lines used to be reported as broken frontmatter.
    text = "# why this skill is shelved\npolicy:\n  # explicit invocation only\n  allow_implicit_invocation: false\n"
    data, bad, _ = sa.parse_frontmatter("---\n" + text + "---\n", nested_policy=True)
    assert not bad, "comment lines must not be reported as fields: %s" % bad
    assert sa.bool_value(data["policy"]["allow_implicit_invocation"]) is False

    data, bad, _ = sa.parse_frontmatter("---\n# leading note\nname: x\ndescription: y\n---\n")
    assert not bad and data["name"] == "x", (data, bad)


def test_wrong_shaped_config_is_dropped_not_fatal():
    # Valid TOML, wrong schema. Every one of these used to raise out of the run
    # and exit 3 instead of producing a finding.
    for bad in ({"overlap": {"suppress": 7}}, {"pocket": {"skills": 5}},
                {"budget": {"context_window": "nope"}}, {"budget": {"context_window": True}},
                {"budget": {"context_window": -5}}, {"ownership": ["x"]}, {"overlap": "nope"},
                "not a table"):
        clean, problems = sa.validated_config(bad)
        assert problems, "wrong-shaped config must be reported: %r" % (bad,)
        sa.overlap_report([], clean, [])
        sa.budget_report([], clean, [])
        sa.pocket_report([], clean, [])

    good = {"pocket": {"skills": ["a"]}, "ownership": {"job": "a"},
            "overlap": {"suppress": ["a / b"]}, "budget": {"context_window": 300000},
            "unknown-section": {"left": "alone"}}
    clean, problems = sa.validated_config(good)
    assert not problems, problems
    assert clean == good, clean


def test_overlap_suppression():
    shared = "alpha bravo charlie delta echo foxtrot"
    named = [{"name": "a", "real_path": "/x/a", "description": shared},
             {"name": "b", "real_path": "/x/b", "description": shared}]
    paths = [{"name": "dup", "real_path": "/home/dup", "description": shared},
             {"name": "dup", "real_path": "/repo/dup", "description": shared}]

    findings = []
    assert sa.overlap_report(named, {"overlap": {"suppress": ["a / b"]}}, findings)[0]["suppressed"]
    assert not findings, "a suppressed pair must not produce a finding: %s" % findings

    # A label pair is two real paths when names collide. Splitting on the first
    # slash instead of " / " matched nothing and suppressed nothing, silently.
    findings = []
    assert sa.overlap_report(paths, {"overlap": {"suppress": ["/home/dup / /repo/dup"]}}, findings)[0]["suppressed"]
    assert not findings, "a path-labelled pair must be suppressible: %s" % findings

    findings = []
    sa.overlap_report(named, {"overlap": {"suppress": ["a / b", "gone / nope", "typo"]}}, findings)
    stale = sorted(f["skill"] for f in findings if f["code"] == "suppress_unmatched")
    assert stale == ["gone / nope", "typo"], stale

    findings = []
    assert not sa.overlap_report(named, {}, findings)[0]["suppressed"]
    assert [f["code"] for f in findings] == ["overlap"], findings


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
                              strict=False, version=False, home=str(tmp))
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
        # Below the root: a scan that only reads the root's own children misses it.
        (skills / "group").mkdir()
        (skills / "group/dangling").symlink_to(tmp / "also-nowhere")

        report = run(tmp)
        by_name = {s["name"]: s for s in report["skills"]}
        codes = {f["code"] for f in report["findings"]}

        assert by_name["shelved"]["states"]["claude"] == "SHELF", by_name["shelved"]
        assert "no_frontmatter" in codes, codes
        assert "broken_symlink" in codes, "a dangling link must not stop the scan"
        dead = {f["path"] for f in report["findings"] if f["code"] == "broken_symlink"}
        assert str(skills / "group/dangling") in dead, dead
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


def test_dangling_skill_reference_is_reported_and_live_one_is_not():
    tmp = Path(tempfile.mkdtemp())
    try:
        (tmp / "repo").mkdir()
        root = tmp / "global/claude"
        write_skill(root, "planner", '---\nname: planner\ndescription: "Plans work. Use when the user asks to plan."\n---\n'
                                     "Then follow skills/incremental-implementation/SKILL.md and skills/builder/SKILL.md.\n")
        write_skill(root, "builder", '---\nname: builder\ndescription: "Builds work. Use when the user asks to build."\n---\nbody\n')
        report = run(tmp)
        missing = [item["missing"] for item in report["dangling_references"]]
        assert missing == ["incremental-implementation"], missing
        assert any(f["code"] == "dangling_reference" for f in report["findings"])
    finally:
        shutil.rmtree(tmp)


def test_trigger_phrase_contained_in_another_is_a_notice_not_a_verdict():
    tmp = Path(tempfile.mkdtemp())
    try:
        (tmp / "repo").mkdir()
        root = tmp / "global/claude"
        write_skill(root, "quick", '---\nname: quick\ndescription: "Use when the user says \'debug React component\'."\n---\nbody\n')
        write_skill(root, "deep", '---\nname: deep\ndescription: "Use when the user says \'debug React component rendering performance\'."\n---\nbody\n')
        report = run(tmp)
        shadows = [f for f in report["findings"] if f["code"] == "intent_shadow"]
        assert len(shadows) == 1, [f["message"] for f in shadows]
        assert "debug react component" in shadows[0]["message"]
        # Containment is a hint about model routing, not a proven failure, so it
        # must never be the thing that fails a --strict run on its own.
        assert shadows[0]["severity"] == "notice", shadows[0]
        assert any("is contained in" in line for line in sa.lines_for(report))
        # An identical phrase is plain overlap, not shadowing.
        assert not sa.phrase_shadows('says "run tests"', 'says "run tests"')
        # One word matches too much to mean anything.
        assert not sa.phrase_shadows('says "debug"', 'says "debug React component"')
    finally:
        shutil.rmtree(tmp)


def test_github_format_emits_escaped_annotations():
    tmp = Path(tempfile.mkdtemp())
    try:
        (tmp / "repo").mkdir()
        write_skill(tmp / "global/claude", "thin", '---\nname: thin\ndescription: "Use when: asked"\n---\nbody\n')
        report = run(tmp)
        lines = sa.github_lines(report)
        assert lines and all(line.startswith(("::error ", "::warning ", "::notice ")) for line in lines), lines
        annotated = [line for line in lines if "SKILL.md" in line]
        assert annotated, "skill findings must annotate the SKILL.md, not its directory"
        assert sa.gh_escape("a,b:c%d") == "a%2Cb%3Ac%25d", "property separators must not survive in a value"
        assert sa.gh_escape("a,b:c", data=True) == "a,b:c", "message data only escapes %% and newlines"
    finally:
        shutil.rmtree(tmp)


def test_portable_frontmatter_limits_are_structural_errors():
    tmp = Path(tempfile.mkdtemp())
    try:
        (tmp / "repo").mkdir()
        root = tmp / "global/claude"
        write_skill(root, "Bad_Name",
                    '---\nname: Bad_Name\ndescription: "Reviews a skill. Use when the user asks."\n---\nbody\n')
        write_skill(root, "long-description",
                    '---\nname: long-description\ndescription: "%s"\n---\nbody\n'
                    % ("Use when the user asks for validation. " + "x" * 1024))
        write_skill(root, "bad-compatibility",
                    '---\nname: bad-compatibility\n'
                    'description: "Reviews a skill. Use when the user asks."\n'
                    'compatibility: [%s]\n---\nbody\n' % ("x" * 501))
        write_skill(root, "bad-metadata",
                    '---\nname: bad-metadata\n'
                    'description: "Reviews a skill. Use when the user asks."\n'
                    'metadata: [one, two]\n---\nbody\n')
        report = run(tmp)
        errors = {(item["skill"], item["code"]) for item in report["findings"]
                  if item["severity"] == "error"}
        assert ("Bad_Name", "invalid_name") in errors, errors
        assert ("long-description", "invalid_description") in errors, errors
        assert ("bad-compatibility", "invalid_compatibility") in errors, errors
        assert ("bad-metadata", "invalid_metadata") in errors, errors
    finally:
        shutil.rmtree(tmp)


def test_codex_enabled_false_disables_the_configured_skill_on_python39_fallback():
    tmp = Path(tempfile.mkdtemp())
    try:
        (tmp / "repo").mkdir()
        root = tmp / "global/codex"
        disabled = write_skill(root, "codex-off",
                               '---\nname: codex-off\n'
                               'description: "Reviews a skill. Use when the user asks."\n---\nbody\n')
        enabled = write_skill(root, "codex-on",
                              '---\nname: codex-on\n'
                              'description: "Reviews a skill. Use when the user asks."\n---\nbody\n')
        (tmp / ".codex").mkdir()
        (tmp / ".codex/config.toml").write_text(
            'model = "gpt"\n\n[[skills.config]]\npath = "%s"\nenabled = false\n\n'
            '[[skills.config]]\npath = "%s"\nenabled = true\n'
            % (disabled / "SKILL.md", enabled / "SKILL.md"), encoding="utf-8")
        audit_config = tmp / "audit.toml"
        audit_config.write_text('[pocket]\nskills = ["codex-off", "codex-on"]\n', encoding="utf-8")
        report = run(tmp, tool=None, config=str(audit_config))
        states = {skill["name"]: skill["states"]["codex"] for skill in report["skills"]}
        assert states == {"codex-off": "DISABLED", "codex-on": "POCKET"}, states
        off = next(skill for skill in report["skills"] if skill["name"] == "codex-off")
        assert off["host_overrides"]["codex"] == "disabled", off
        assert report["pocket_check"]["pocket_count"] == 1, report["pocket_check"]
        assert report["pocket_check"]["intended_pocket_but_shelf"] == ["codex-off"]
    finally:
        shutil.rmtree(tmp)


def test_codex_disabled_path_matches_through_a_tool_symlink():
    tmp = Path(tempfile.mkdtemp())
    try:
        (tmp / "repo").mkdir()
        canonical = write_skill(tmp / "canonical", "linked-off",
                                '---\nname: linked-off\n'
                                'description: "Reviews a skill. Use when the user asks."\n---\nbody\n')
        tool_root = tmp / "global/codex"
        tool_root.mkdir(parents=True)
        (tool_root / "linked-off").symlink_to(canonical, target_is_directory=True)
        (tmp / ".codex").mkdir()
        (tmp / ".codex/config.toml").write_text(
            '[[skills.config]]\npath = "%s"\nenabled = false\n'
            % (tool_root / "linked-off/SKILL.md"), encoding="utf-8")
        report = run(tmp, tool=["codex"])
        assert report["skills"][0]["real_path"] == str(canonical.resolve())
        assert report["skills"][0]["states"]["codex"] == "DISABLED", report["skills"][0]
    finally:
        shutil.rmtree(tmp)


def test_codex_wrong_skills_config_shape_is_reported_once_and_fails_soft():
    tmp = Path(tempfile.mkdtemp())
    try:
        (tmp / "repo").mkdir()
        write_skill(tmp / "global/codex", "codex-skill",
                    '---\nname: codex-skill\n'
                    'description: "Reviews a skill. Use when the user asks."\n---\nbody\n')
        (tmp / ".codex").mkdir()
        (tmp / ".codex/config.toml").write_text(
            '[skills]\nconfig = "not-an-array"\n', encoding="utf-8")
        report = run(tmp, tool=["codex"])
        errors = [item for item in report["findings"] if item["code"] == "config_error"]
        assert len(errors) == 1 and "array of tables" in errors[0]["message"], errors
        assert report["skills"][0]["states"]["codex"] == "UNKNOWN", report["skills"][0]
    finally:
        shutil.rmtree(tmp)


def test_claude_skill_overrides_replace_frontmatter_visibility():
    tmp = Path(tempfile.mkdtemp())
    try:
        (tmp / "repo").mkdir()
        root = tmp / "global/claude"
        body = ('---\nname: %s\ndescription: "Reviews a skill. Use when the user asks."\n'
                'disable-model-invocation: true\n---\nbody\n')
        for name in ("forced-on", "name-only", "menu-only", "claude-off"):
            write_skill(root, name, body % name)
        (tmp / ".claude").mkdir()
        (tmp / ".claude/settings.json").write_text(json.dumps({"skillOverrides": {
            "forced-on": "on", "name-only": "name-only",
            "menu-only": "user-invocable-only", "claude-off": "off"}}), encoding="utf-8")
        report = run(tmp, tool=["claude"])
        by_name = {skill["name"]: skill for skill in report["skills"]}
        states = {name: skill["states"]["claude"] for name, skill in by_name.items()}
        assert states == {"claude-off": "DISABLED", "forced-on": "POCKET",
                          "menu-only": "SHELF", "name-only": "POCKET"}, states
        assert by_name["name-only"]["listing_descriptions"]["claude"] == ""
        assert report["budget"]["claude"]["total"] == (
            len("forced-on") + len(by_name["forced-on"]["description"]) + len("name-only"))
    finally:
        shutil.rmtree(tmp)


def test_gemini_persistent_settings_make_enabled_state_readable_and_union_disabled_names():
    tmp = Path(tempfile.mkdtemp())
    try:
        (tmp / "repo").mkdir()
        body = '---\nname: %s\ndescription: "Reviews a skill. Use when the user asks."\n---\nbody\n'
        for name in ("user-off", "workspace-off", "still-on"):
            write_skill(tmp / "global/gemini", name, body % name)
        (tmp / ".gemini").mkdir()
        (tmp / ".gemini/settings.json").write_text(
            json.dumps({"skills": {"disabled": ["user-off"]}}), encoding="utf-8")
        (tmp / "repo/.gemini").mkdir()
        (tmp / "repo/.gemini/settings.json").write_text(
            json.dumps({"skills": {"disabled": ["workspace-off"]}}), encoding="utf-8")
        report = run(tmp, tool=["gemini"])
        by_name = {skill["name"]: skill for skill in report["skills"]}
        assert {name: skill["states"]["gemini"] for name, skill in by_name.items()} == {
            "still-on": "POCKET", "user-off": "DISABLED", "workspace-off": "DISABLED"}
        assert by_name["user-off"]["host_overrides"]["gemini"] == "disabled"
        assert report["budget"]["gemini"]["pocket_skills"] == 1, report["budget"]
    finally:
        shutil.rmtree(tmp)


def test_gemini_skills_enabled_false_disables_every_visible_skill():
    tmp = Path(tempfile.mkdtemp())
    try:
        (tmp / "repo").mkdir()
        write_skill(tmp / "global/gemini", "gem-off",
                    '---\nname: gem-off\ndescription: "Reviews a skill. Use when the user asks."\n---\nbody\n')
        (tmp / ".gemini").mkdir()
        (tmp / ".gemini/settings.json").write_text(
            json.dumps({"skills": {"enabled": False}}), encoding="utf-8")
        skill = run(tmp, tool=["gemini"])["skills"][0]
        assert skill["states"]["gemini"] == "DISABLED", skill
    finally:
        shutil.rmtree(tmp)


def test_gemini_enabled_vs_claude_shelf_is_not_an_impossible_mode_disagreement():
    tmp = Path(tempfile.mkdtemp())
    try:
        (tmp / "repo").mkdir()
        canonical = write_skill(tmp / "canonical", "shared",
                                '---\nname: shared\n'
                                'description: "Reviews a skill. Use when the user asks."\n'
                                'disable-model-invocation: true\n---\nbody\n')
        for tool in ("claude", "gemini"):
            root = tmp / "global" / tool
            root.mkdir(parents=True)
            (root / "shared").symlink_to(canonical, target_is_directory=True)
        report = run(tmp, tool=["claude", "gemini"])
        assert report["skills"][0]["states"] == {
            "claude": "SHELF", "gemini": "POCKET"}, report["skills"][0]
        assert not any(item["code"] == "mode_disagreement" for item in report["findings"])
    finally:
        shutil.rmtree(tmp)


def test_malformed_host_override_files_fail_soft_with_config_findings():
    tmp = Path(tempfile.mkdtemp())
    try:
        (tmp / "repo").mkdir()
        body = '---\nname: %s\ndescription: "Reviews a skill. Use when the user asks."\n---\nbody\n'
        write_skill(tmp / "global/claude", "claude-skill", body % "claude-skill")
        codex_skill = write_skill(tmp / "global/codex", "codex-skill", body % "codex-skill")
        write_skill(tmp / "global/gemini", "gemini-skill", body % "gemini-skill")
        (tmp / ".claude").mkdir()
        (tmp / ".claude/settings.json").write_text("{not-json", encoding="utf-8")
        (tmp / ".codex").mkdir()
        (tmp / ".codex/config.toml").write_text(
            '[[skills.config]]\npath = "%s"\nenabled = "not-a-boolean"\n'
            % (codex_skill / "SKILL.md"), encoding="utf-8")
        (tmp / ".gemini").mkdir()
        (tmp / ".gemini/settings.json").write_text(
            json.dumps({"skills": {"disabled": "not-a-list"}}), encoding="utf-8")
        report = run(tmp, tool=["claude", "codex", "gemini"])
        host_errors = [item for item in report["findings"] if item["code"] == "config_error"]
        assert len(host_errors) == 3, host_errors
        assert {skill["name"] for skill in report["skills"]} == {
            "claude-skill", "codex-skill", "gemini-skill"}
        assert {skill["name"]: next(iter(skill["states"].values()))
                for skill in report["skills"]} == {
                    "claude-skill": "UNKNOWN",
                    "codex-skill": "UNKNOWN",
                    "gemini-skill": "UNKNOWN",
                }, report["skills"]
    finally:
        shutil.rmtree(tmp)


def test_unknown_only_selected_tool_is_not_reported_as_shelf_drift():
    tmp = Path(tempfile.mkdtemp())
    try:
        (tmp / "repo").mkdir()
        write_skill(tmp / "global/antigravity", "wanted",
                    '---\nname: wanted\ndescription: "Reviews a skill. Use when the user asks."\n---\nbody\n')
        config = tmp / "audit.toml"
        config.write_text('[pocket]\nskills = ["wanted", "installed-elsewhere"]\n\n'
                          '[overlap]\nsuppress = ["also / elsewhere"]\n', encoding="utf-8")
        report = run(tmp, tool=["antigravity"], config=str(config))
        pocket = report["pocket_check"]
        assert pocket["intended_mode_unknown"] == ["wanted"], pocket
        assert pocket["intended_not_visible"] == ["installed-elsewhere"], pocket
        assert pocket["intended_but_not_installed"] == [], pocket
        assert pocket["intended_pocket_but_shelf"] == [], pocket
        assert not any(item["code"] == "intended_pocket_shelf" for item in report["findings"])
        assert not any(item["code"] in ("intended_missing", "suppress_unmatched")
                       for item in report["findings"]), report["findings"]
    finally:
        shutil.rmtree(tmp)


def test_filtered_nonpocket_state_is_informational_when_an_excluded_host_may_satisfy_intent():
    findings = []
    skills = [{"name": "wanted", "library": "local", "scopes": ["global"],
               "states": {"claude": "SHELF"}}]
    result = sa.pocket_report(skills, {"pocket": {"skills": ["wanted"]}}, findings,
                              filtered=True)
    assert result["intended_selected_nonpocket"] == ["wanted"], result
    assert result["intended_pocket_but_shelf"] == [], result
    assert not findings, findings


def test_unfiltered_pocket_check_still_reports_truly_missing_config_names():
    findings = []
    result = sa.pocket_report([], {"pocket": {"skills": ["gone"]}}, findings)
    assert result["intended_but_not_installed"] == ["gone"], result
    assert result["intended_not_visible"] == [], result
    assert [item["code"] for item in findings] == ["intended_missing"], findings


def test_antigravity_discovers_documented_and_legacy_workspace_roots():
    tmp = Path(tempfile.mkdtemp())
    try:
        write_skill(tmp / "repo/.agents/skills", "documented",
                    '---\nname: documented\ndescription: "Reviews a skill. Use when the user asks."\n---\nbody\n')
        write_skill(tmp / "repo/.agent/skills", "legacy",
                    '---\nname: legacy\ndescription: "Reviews a skill. Use when the user asks."\n---\nbody\n')
        report = run(tmp, tool=["antigravity"])
        assert {skill["name"] for skill in report["skills"]} == {"documented", "legacy"}
        assert all(skill["states"]["antigravity"] == "UNKNOWN" for skill in report["skills"])
    finally:
        shutil.rmtree(tmp)


def test_antigravity_global_path_matches_current_vendor_documentation():
    assert sa.GLOBAL_PATHS["antigravity"] == ("~/.gemini/config/skills",)
    assert "~/.gemini/antigravity/skills" in sa.ANTIGRAVITY_NON_PORTABLE
    assert "~/.gemini/antigravity-cli/skills" in sa.ANTIGRAVITY_NON_PORTABLE


def test_desktop_invocation_mode_comes_from_the_manifest():
    """Desktop's 'enabled' is its disable-model-invocation; guessing is not allowed."""
    tmp = Path(tempfile.mkdtemp())
    try:
        (tmp / "repo").mkdir()
        root = tmp / "global/claude-desktop"
        for name in ("switched-off", "switched-on", "unlisted"):
            write_skill(root, name, '---\nname: %s\ndescription: "Does a thing. Use when the user asks."\n---\nbody\n' % name)
        # The manifest sits beside the skills directory, as it does on disk.
        (tmp / "global/manifest.json").write_text(json.dumps({"skills": [
            {"name": "switched-off", "enabled": False}, {"name": "switched-on", "enabled": True}]}), encoding="utf-8")
        states = {s["name"]: s["states"]["claude-desktop"] for s in run(tmp, tool=["claude-desktop"])["skills"]}
        assert states == {"switched-off": "SHELF", "switched-on": "POCKET", "unlisted": "UNKNOWN"}, states
    finally:
        shutil.rmtree(tmp)


def test_desktop_absent_or_non_boolean_enabled_is_unknown_not_shelf():
    """bool() coercion would invent SHELF for a mode the manifest never stated."""
    tmp = Path(tempfile.mkdtemp())
    try:
        (tmp / "repo").mkdir()
        root = tmp / "global/claude-desktop"
        names = ("no-key", "string-true", "number-one", "null-value", "real-false")
        for name in names:
            write_skill(root, name, '---\nname: %s\ndescription: "Does a thing. Use when the user asks."\n---\nbody\n' % name)
        (tmp / "global/manifest.json").write_text(json.dumps({"skills": [
            {"name": "no-key"},                      # entry present, mode never stated
            {"name": "string-true", "enabled": "true"},
            {"name": "number-one", "enabled": 1},
            {"name": "null-value", "enabled": None},
            {"name": "real-false", "enabled": False}]}), encoding="utf-8")
        states = {s["name"]: s["states"]["claude-desktop"] for s in run(tmp, tool=["claude-desktop"])["skills"]}
        assert states == {"no-key": "UNKNOWN", "string-true": "UNKNOWN", "number-one": "UNKNOWN",
                          "null-value": "UNKNOWN", "real-false": "SHELF"}, states
    finally:
        shutil.rmtree(tmp)


def test_desktop_pocket_is_counted_but_not_judged_against_the_config():
    """The config cannot switch a Desktop skill off, so it must not grade one."""
    tmp = Path(tempfile.mkdtemp())
    try:
        (tmp / "repo").mkdir()
        body = '---\nname: %s\ndescription: "Does a thing. Use when the user asks."\n---\nbody\n'
        # `shared` exists in both libraries: pocket in Desktop, correctly shelved
        # locally. Keying on the name alone reported it as drift.
        write_skill(tmp / "global/claude-desktop", "desk-only", body % "desk-only")
        write_skill(tmp / "global/claude-desktop", "shared", body % "shared")
        write_skill(tmp / "global/claude", "shared",
                    '---\nname: shared\ndescription: "Does a thing. Use when the user asks."\n'
                    'disable-model-invocation: true\n---\nbody\n')
        (tmp / "global/manifest.json").write_text(json.dumps({"skills": [
            {"name": "desk-only", "enabled": True}, {"name": "shared", "enabled": True}]}), encoding="utf-8")
        config = tmp / "audit.toml"
        config.write_text('[pocket]\nskills = []\n', encoding="utf-8")
        report = run(tmp, tool=["claude", "claude-desktop"], config=str(config))
        pocket = report["pocket_check"]
        assert pocket["intended_shelf_but_pocket"] == [], pocket["intended_shelf_but_pocket"]
        assert sorted(pocket["desktop_pocket"]) == ["desk-only", "shared"], pocket["desktop_pocket"]
        assert pocket["pocket_count"] == 2, "Desktop skills are still counted, just not judged"
        assert not any(f["code"] == "intended_shelf_pocket" for f in report["findings"])
    finally:
        shutil.rmtree(tmp)


def test_vendor_skill_quality_findings_are_demoted_to_notice():
    """A vendor's wording is not your bug and must never fail --strict."""
    tmp = Path(tempfile.mkdtemp())
    try:
        (tmp / "repo").mkdir()
        long_desc = "Use when the user asks. " + ("padding words here " * 30)
        write_skill(tmp / "global/claude-desktop", "vendor-bloat",
                    '---\nname: vendor-bloat\ndescription: "%s"\n---\nbody\n' % long_desc)
        write_skill(tmp / "global/claude", "mine-bloat",
                    '---\nname: mine-bloat\ndescription: "%s"\n---\nbody\n' % long_desc)
        report = run(tmp, tool=["claude", "claude-desktop"])
        sev = {f["skill"]: f["severity"] for f in report["findings"] if f["code"] == "bloated_description"}
        assert sev.get("vendor-bloat") == "notice", sev
        assert sev.get("mine-bloat") == "warning", "your own skills keep full severity: %s" % sev
        assert any("[vendor-installed]" in f["message"] for f in report["findings"]
                   if f["skill"] == "vendor-bloat"), "the demotion must say why"
        # is_vendor also covers Codex's bundled .system tree, by path.
        assert sa.is_vendor("/home/u/.codex/skills/.system/skill-creator")
        assert not sa.is_vendor("/home/u/.skills/my-skill")
    finally:
        shutil.rmtree(tmp)


def test_vendor_name_does_not_demote_a_same_named_local_overlap():
    """Vendor provenance belongs to an occurrence, never to a global name."""
    tmp = Path(tempfile.mkdtemp())
    try:
        (tmp / "repo").mkdir()
        shared = ('---\nname: %s\n'
                  'description: "Alpha bravo charlie delta echo foxtrot. Use when the user asks."\n'
                  '---\nbody\n')
        for name in ("idea-one", "idea-two"):
            write_skill(tmp / "global/claude", name, shared % name)
            write_skill(tmp / "global/claude-desktop", name, shared % name)
        report = run(tmp, tool=["claude", "claude-desktop"])
        local_pair = next(item for item in report["overlaps"]
                          if set(item["skills"]) == {"idea-one", "idea-two"}
                          and not item["vendor_installed"])
        assert local_pair["severity"] == "warning", local_pair
        local_findings = [item for item in report["findings"]
                          if item["code"] == "overlap"
                          and item["skill"] == "idea-one / idea-two"
                          and not item.get("vendor_installed")]
        assert local_findings and local_findings[0]["severity"] == "warning", local_findings
        assert "[vendor-installed]" not in local_findings[0]["message"]
    finally:
        shutil.rmtree(tmp)


def test_vendor_unparseable_frontmatter_is_demoted_too():
    """A vendor's unsupported nested field is still outside the user's control."""
    tmp = Path(tempfile.mkdtemp())
    try:
        (tmp / "repo").mkdir()
        broken = ('---\nname: %s\ndescription: "Does a thing. Use when the user asks."\n'
                  'custom:\n  version: 1\n---\nbody\n')
        write_skill(tmp / "global/codex/.system", "vendor-broken", broken % "vendor-broken")
        write_skill(tmp / "global/codex", "mine-broken", broken % "mine-broken")
        report = run(tmp, tool=["codex"])
        sev = {f["skill"]: f["severity"] for f in report["findings"] if f["code"] == "unparseable_field"}
        assert sev.get("vendor-broken") == "notice", sev
        assert sev.get("mine-broken") == "warning", "your own broken frontmatter still fails: %s" % sev
    finally:
        shutil.rmtree(tmp)


def test_a_name_pocket_in_both_libraries_counts_once():
    """pocket_count is by distinct name, matching the rule the section prints."""
    tmp = Path(tempfile.mkdtemp())
    try:
        (tmp / "repo").mkdir()
        body = '---\nname: %s\ndescription: "Does a thing. Use when the user asks."\n---\nbody\n'
        for lib in ("global/claude-desktop", "global/claude"):
            write_skill(tmp / lib, "synced", body % "synced")
        (tmp / "global/manifest.json").write_text(json.dumps({"skills": [
            {"name": "synced", "enabled": True}]}), encoding="utf-8")
        report = run(tmp, tool=["claude", "claude-desktop"])
        assert report["pocket_check"]["pocket_count"] == 1, "one name synced to two libraries is one skill"
    finally:
        shutil.rmtree(tmp)


def test_desktop_and_local_libraries_are_never_compared():
    """A name synced to both is one skill in two libraries, not a collision."""
    tmp = Path(tempfile.mkdtemp())
    try:
        (tmp / "repo").mkdir()
        shared = '---\nname: %s\ndescription: "Alpha bravo charlie delta echo foxtrot. Use when the user asks."\n---\nbody\n'
        write_skill(tmp / "global/claude", "dup", shared % "dup")
        write_skill(tmp / "global/claude-desktop", "dup", shared % "dup")
        # A control pair inside ONE library must still be caught, or this test
        # would pass just as well against an overlap check that does nothing.
        write_skill(tmp / "global/claude-desktop", "twin", shared % "twin")
        report = run(tmp, tool=["claude", "claude-desktop"])
        assert report["collisions"] == [], report["collisions"]
        assert not any(f["code"] == "name_collision" for f in report["findings"])
        pairs = {tuple(sorted(o["skills"])) for o in report["overlaps"]}
        assert ("dup", "twin") in pairs, "same-library overlap must still fire: %s" % pairs
        assert ("dup", "dup") not in pairs, "cross-library pair must not be compared: %s" % pairs
    finally:
        shutil.rmtree(tmp)


def test_glob_location_reports_itself_when_it_matches_nothing():
    """A location that vanishes from the summary is the failure this tool prevents."""
    tmp = Path(tempfile.mkdtemp())
    try:
        assert sa.expand_root(str(tmp / "*/skills")) == [Path(str(tmp / "*/skills"))]
        (tmp / "abc/skills").mkdir(parents=True)
        (tmp / "xyz/skills").mkdir(parents=True)
        assert sa.expand_root(str(tmp / "*/skills")) == [tmp / "abc/skills", tmp / "xyz/skills"]
        assert sa.expand_root(str(tmp / "abc/skills")) == [tmp / "abc/skills"], "a plain path is untouched"
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
