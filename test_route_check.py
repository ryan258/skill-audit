#!/usr/bin/env python3
"""Self-check for route_check. Run: python3 test_route_check.py

The model call is stubbed — this covers the grading, not the routing. Whether
the model picks correctly is what the harness itself is for.
"""
import argparse
import tempfile
from pathlib import Path

import route_check as rc

LISTING = [("dhp-context-sync", "Syncs shell context."), ("brand-voice", "Writes posts.")]
CASES = [{"query": "sync my shell", "expected": "dhp-context-sync"},
         {"query": "fix my .bashrc", "expected": None}]


def test_grading_is_exact_and_none_is_a_real_expectation():
    assert rc.matches("dhp-context-sync", "dhp-context-sync")
    assert rc.matches("dhp-context-sync", " DHP-Context-Sync \n"), "answers arrive with stray case and space"
    assert rc.matches(None, "NONE") and rc.matches(None, "none")
    assert not rc.matches(None, "dhp-context-sync"), "a skill firing when none should is a failure"
    assert not rc.matches("dhp-context-sync", "brand-voice")
    assert not rc.matches("dhp-context-sync", "ERROR: claude exited 1"), "a harness error is never a pass"


def test_repeat_reports_a_rate_not_a_verdict():
    answers = iter(["dhp-context-sync", "brand-voice", "dhp-context-sync", "NONE", "NONE", "NONE"])
    results = rc.run_cases(CASES, LISTING, "stub", repeat=3, jobs=1, ask=lambda *a: next(answers))
    assert results[0]["passed"] == 2 and results[0]["rate"] < 1, results[0]
    assert results[1]["rate"] == 1, results[1]
    lines = "\n".join(rc.report_lines(results, LISTING))
    assert "FAIL  2/3" in lines and "PASS  3/3" in lines, lines
    assert "got: brand-voice" in lines, "a failure must name what fired instead"


def test_expectation_outside_the_listing_is_skipped_not_scored():
    """A shelved skill cannot be routed to, so counting it as a miss is a lie."""
    calls = []
    cases = [{"query": "q", "expected": "shelved-skill"}, {"query": "r", "expected": None}]
    results = rc.run_cases(cases, LISTING, "stub", repeat=2, jobs=1,
                           ask=lambda *a: calls.append(a) or "NONE")
    assert results[0]["skipped"] and results[0]["rate"] is None, results[0]
    assert len(calls) == 2, "a skipped case must cost no model calls, got %d" % len(calls)
    lines = "\n".join(rc.report_lines(results, LISTING))
    assert "SKIP" in lines and "not in the pocket listing" in lines, lines
    assert "1/1 completed cases passed every trial; 1 skipped" in lines, lines


def test_skipped_case_alone_does_not_fail_the_run():
    """The documented sample command must not exit 1 purely because of skips."""
    results = rc.run_cases([{"query": "q", "expected": "shelved-skill"}], LISTING, "stub", 1, 1,
                           ask=lambda *a: "NONE")
    assert not any(r["rate"] is not None and r["rate"] < 1 for r in results), results
    assert rc.exit_code_for(results) == 0


def test_harness_errors_are_reported_and_exit_three():
    results = rc.run_cases([CASES[0]], LISTING, "stub", repeat=2, jobs=1,
                           ask=lambda *a: "ERROR: claude timed out")
    assert results[0]["errors"] == ["ERROR: claude timed out", "ERROR: claude timed out"], results
    assert results[0]["rate"] is None, "an incomplete harness run must not receive a routing rate"
    assert rc.exit_code_for(results) == 3, "infrastructure must not masquerade as a routing miss"
    lines = "\n".join(rc.report_lines(results, LISTING))
    assert "ERROR  0/2" in lines and "harness: ERROR: claude timed out" in lines, lines
    assert "0/0 completed cases" in lines and "1 harness-error case not scored" in lines, lines

    misses = rc.run_cases([CASES[0]], LISTING, "stub", repeat=1, jobs=1,
                           ask=lambda *a: "brand-voice")
    assert rc.exit_code_for(misses) == 1, "a genuine wrong skill remains a routing failure"


def test_pocket_listing_respects_name_only_descriptions():
    original = rc.sa.build_report
    rc.sa.build_report = lambda args: {"skills": [
        {"name": "name-only", "description": "hidden", "library": "local",
         "states": {"claude": "POCKET"}, "listing_descriptions": {"claude": ""}},
        {"name": "disabled", "description": "hidden", "library": "local",
         "states": {"claude": "DISABLED"}, "listing_descriptions": {"claude": "hidden"}},
    ]}
    try:
        args = argparse.Namespace(repo=[], config=None, tool=["claude"])
        assert rc.pocket_listing(args) == [("name-only", "")]
    finally:
        rc.sa.build_report = original


def test_repeat_below_one_is_rejected_at_parse_time():
    for bad in ("0", "-3"):
        try:
            rc.positive_int(bad)
            raise AssertionError("--repeat %s must be rejected, not divided by" % bad)
        except argparse.ArgumentTypeError as exc:
            assert "1 or more" in str(exc), exc
    assert rc.positive_int("1") == 1


def test_malformed_case_file_fails_loudly():
    tmp = Path(tempfile.mkdtemp()) / "cases.jsonl"
    tmp.write_text('{"query": "q"}\n', encoding="utf-8")
    try:
        rc.load_cases(tmp)
        raise AssertionError("a case with no \"expected\" must not silently pass")
    except SystemExit as exc:
        assert "expected" in str(exc), exc
    tmp.write_text('# comment\n\n{"query": "q", "expected": null}\n', encoding="utf-8")
    assert len(rc.load_cases(tmp)) == 1, "comments and blank lines are skipped"


def test_non_string_expected_is_rejected_with_its_line_number():
    """Grading calls .casefold(); a stray int must fail at load, not mid-run."""
    tmp = Path(tempfile.mkdtemp()) / "cases.jsonl"
    for bad in ('{"query": "q", "expected": 1}', '{"query": "q", "expected": ["a"]}',
                '{"query": "q", "expected": "  "}'):
        tmp.write_text('{"query": "ok", "expected": null}\n' + bad + "\n", encoding="utf-8")
        try:
            rc.load_cases(tmp)
            raise AssertionError("must reject %s" % bad)
        except SystemExit as exc:
            assert "line 2" in str(exc), exc


if __name__ == "__main__":
    tests = [value for key, value in sorted(globals().items()) if key.startswith("test_")]
    for test in tests:
        test()
        print("ok  %s" % test.__name__)
    print("\n%d passed" % len(tests))
