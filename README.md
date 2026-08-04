# skill-audit

A read-only CLI that finds every `SKILL.md` on your Mac and tells you what's wrong with your agent skill library — across [Claude Code](https://docs.anthropic.com/en/docs/agents-and-tools/claude-code/overview), [Codex](https://openai.com), [Gemini CLI](https://gemini.google.com), and [Antigravity](https://antigravity.google).

It never modifies a skill file. The only path it can write to is the one you pass to `--markdown`.

## Start with the library model

Before choosing paths or flags, read [The skill-library model](docs/library-model.md).
It separates the three things that are easy to conflate: the canonical personal
copy, a tool's discovery and collision rules, and that tool's invocation mode.

## Run it

```sh
python3 skill_audit.py
```

Python 3, standard library only. No installs, no network calls. `tomllib` (3.11+) is used for the config file when available; on older Pythons a small fallback parser handles the documented config shape.

## Vocabulary

The report uses three words consistently. They're this tool's terms, not vendor wording.

| Term | Meaning |
|---|---|
| **POCKET** | The agent can invoke it on its own. Its description sits in context every session. |
| **SHELF** | Explicit invocation only. The agent won't reach for it. |
| **UNKNOWN** | The tool has no documented flag for this, so the state can't be determined. |

`UNKNOWN` is an expected state, not a failure. Gemini CLI and Antigravity have no documented way to block auto-invocation, so skills visible only to those two always report `UNKNOWN` — and are excluded from budget totals, with the excluded count printed so the number isn't mistaken for a full picture.

## What it checks

**Per skill** — frontmatter parses; `description` present; `name` matches the directory; description length, trigger language, vagueness, front-loading; body over 500 lines; invocation mode *per tool* (`disable-model-invocation` for Claude, `agents/openai.yaml` → `policy.allow_implicit_invocation` for Codex).

**Claude Desktop** is scanned as a *separate library* — vendor-documented behavior: Cowork and cloud sessions do not read `~/.claude/skills/`, they load the skills enabled for your claude.ai account. Its skills sync from your account (including Anthropic's own built-ins), cached under two app-assigned identifiers, and its invocation mode comes from that cache's `manifest.json` `enabled` flag rather than `disable-model-invocation`. Because that library never shares a listing with your local one, name collisions and overlap are scoped per library — a skill present in both is two libraries agreeing, not a conflict. Its listing size is reported but not graded: no published budget exists, and inventing one would manufacture a verdict the vendor never stated.

**Across skills** — name collisions (every location, plus which copy actually wins under each tool's documented precedence, plus Gemini's within-tier preference for `.agents/skills` over `.gemini/skills` — observed, not vendor-documented: re-checked 2026-08-04, the Gemini docs call the two "aliases" and state no within-tier order, but `gemini skills list --all` prints which path overrides which), description overlap candidates, trigger-phrase containment (one quoted trigger is a whole-word slice of another — a hint that the pair competes, not proof that either is unreachable; which one gets picked is the model's call), dangling `skills/<name>/SKILL.md` references to skills that aren't installed, context-budget math, and intended-vs-actual pocket count.

Budgets are counted **per tool**: a skill shelved in Claude but pocket in Codex costs Codex's listing and not Claude's. The pocket check is deliberately broader — a skill counts as pocket if *any* tool that can see it will auto-invoke it — so the two numbers can legitimately disagree. Both print the rule they used.

The pocket check compares **global-scope skills only** against your config. A repo's own skills aren't governed by a global pocket list, so they're counted and listed separately rather than reported as drift.

**Symlinks** — every path is resolved and deduplicated by real target, so one folder reachable from four cupboards reports as one skill with a list of reachable-from paths. Broken symlinks are named and skipped, not fatal. If `~/.gemini/skills` and `~/.agents/skills` resolve to the same target, you get a double-link warning.

## Where it looks

Global (skipped quietly and marked "not present" if absent):

| Tool | Path |
|---|---|
| [Claude Code](https://docs.anthropic.com/en/docs/agents-and-tools/claude-code/overview) | `~/.claude/skills/` |
| [Codex](https://openai.com) + [Gemini CLI](https://gemini.google.com) | `~/.agents/skills/` |
| [Codex](https://openai.com) (legacy) | `~/.codex/skills/` — still scanned; holds the installs on any machine set up before the move |
| [Codex](https://openai.com) (system) | `/etc/codex/skills/` — the documented admin location |
| [Gemini CLI](https://gemini.google.com) (alt) | `~/.gemini/skills/` |
| [Antigravity](https://antigravity.google) | `~/.gemini/config/skills/` |
| Claude Desktop | `~/Library/Application Support/Claude/local-agent-mode-sessions/skills-plugin/*/*/skills` — macOS, globbed; a separate account-synced library |

`~/.gemini/antigravity/skills/` and `~/.gemini/antigravity-cli/skills/` are also scanned and flagged **non-portable** — only `~/.gemini/config/skills/` is confirmed to work across all three Antigravity flavors.

Project scope via `--repo`: `.claude/skills/`, `.agents/skills/`, `.gemini/skills/`, plus nested copies deeper in the tree, reported separately since they load differently.

A skill is any directory containing a `SKILL.md`.

## Flags

| Flag | Effect |
|---|---|
| `--repo PATH` | Add a repo to scan. Repeatable. |
| `--config PATH` | Use a specific config file (default `~/.skill-audit.toml`) |
| `--json` | Emit the full report as JSON instead of text |
| `--format github` | Emit one GitHub workflow command per finding, for inline PR annotations, instead of the text report |
| `--markdown PATH` | Also write a Markdown report to that path |
| `--quiet` | Skip inventory, budget, and pocket check. Errors, warnings, notices, collisions, and overlaps still print. |
| `--tool NAME` | Limit the scan to `claude`, `codex`, `gemini`, `antigravity`, or `claude-desktop`. Repeatable. |
| `--strict` | Treat warnings as failures |
| `--version` | Print version and the `PATHS_VERIFIED` date |

`--json` overrides `--format` and `--quiet` — JSON is always the full structure. `--markdown` always writes the full report. `--quiet` changes what prints, never the exit code.

## Routing harness

`skill_audit.py` never asks a model anything — it reads files. `route_check.py` is the other half: it hands a real model the pocket listing and a request, and checks which skill comes back.

```sh
python3 route_check.py cases/dhp-context-sync.jsonl --repeat 3
```

Cases are JSONL — `{"query": "...", "expected": "skill-name"}`, or `"expected": null` for "no skill should fire". Routing is classification, so grading is string equality: no second model judging prose, nothing to calibrate. Only POCKET skills are offered, because a shelved skill isn't in the model's listing and can't be routed to. A case expecting one is reported as `SKIP`, costs no model calls, and doesn't count toward the pass rate or the exit code — the sample file above ships with three such cases, since `dhp-context-sync` is shelved.

`--repeat N` runs each case N times and reports a rate. Routing is non-deterministic, and a skill that wins 2 times in 3 is the finding. `--model` picks the alias passed to `claude --model` (default `sonnet`); `--jobs` sets how many calls run in parallel (default 8). Both reject values below 1.

It shells out to `claude -p` with `--system-prompt`, so it needs the CLI on PATH, costs tokens, and takes seconds per call. That is why it is a separate file: the auditor stays offline, instant, and dependency-free.

## Exit codes

| Code | Meaning |
|---|---|
| `0` | Clean, or warnings only in default mode |
| `1` | Warnings found and `--strict` was passed |
| `2` | Errors found |
| `3` | Script failure |

Warnings alone don't fail the run. A thin description or a possible overlap is something to read, not something that should break a pipeline.

## Config (optional)

`~/.skill-audit.toml`, or `--config`. Missing is fine — the tool runs on defaults and says so. So is malformed: a value of the wrong shape is ignored with a `config_error` warning and the run continues, because a config file should never be able to abort a read-only audit.

```toml
[pocket]
skills = ["startday", "session-handoff", "brand-voice"]

[ownership]
# Declares which skill owns a job area. Overlap between two skills where
# neither is a declared owner gets bumped from NOTICE to WARNING.
"morning brief" = "startday"
"public content" = "brand-voice"

[overlap]
# Mutes overlap pairs you have read and judged benign. An entry is a pair label
# split on " / " exactly as the report prints it (real paths when two skills
# share a name), or a bare skill name to mute every pair it appears in.
# Muted pairs are still counted in the report; an entry matching nothing warns.
suppress = ["idea-refine / interview-me", "interview-me / grill-me"]

[budget]
context_window = 200000
```

## JSON output

Top-level keys: `meta`, `skills`, `findings`, `collisions`, `overlaps`, `dangling_references`, `budget`, `pocket_check`, `recommendations`. Every finding carries `severity` (`error`/`warning`/`notice`), a stable `code`, `skill`, `path`, and `message` — filter on `code`, not the human text. The code list is a constant at the top of `skill_audit.py`.

## Sample

```text
skill-audit 1.0.0 | paths verified 2026-08-01

Summary
-------
26 unique skills; 17 pocket in at least one tool; 26 discovered entries; 7 locations scanned
config: not present; using defaults
present: /Users/you/.claude/skills
not present: /Users/you/.agents/skills

Errors
------
[unparseable_field] Unparseable field 'description' — a plain scalar cannot contain ': '
  or ' #'; wrap the value in quotes (line 3) — /Users/you/.skills/new-project-kickstart

Name collisions
---------------
brand-voice — 2 copies:
    /Users/you/.skills/brand-voice [global]
    /Users/you/work/app/.claude/skills/brand-voice [project]
    claude:  /Users/you/.skills/brand-voice wins (personal tier)
    gemini:  /Users/you/work/app/.claude/skills/brand-voice wins (workspace tier)
    codex:   Codex does not resolve collisions; the user picks.

Budget
------
Claude: 4533/2000 chars across 17 pocket skills (over)
Codex:  0/4000 chars across 0 pocket skills (pass)
0 skills excluded: only Gemini/Antigravity can see them, and their mode is UNKNOWN
```

Every section prints even when empty, with a "none found" note. A section that silently vanishes looks like a bug.

## Non-goals

1. **It doesn't detect real conflicts.** Two skills can give opposite instructions in prose that shares no keywords. The overlap check is a word-similarity hint — a human still reads the files.
2. **It doesn't fix anything.** No auto-fix mode, not even behind a flag.
3. **It doesn't verify triggering.** Whether a skill fires on a given prompt requires running the agent. That's an eval, not an audit — see `route_check.py` below, which is that eval and is deliberately a separate tool.
4. **It doesn't check Gemini or Antigravity shelf state.** No documented flag exists for either.

## Path instability

These paths moved recently. Codex changed from `~/.codex/skills` to `.agents/skills` — both are scanned, because the old location still holds installs on any machine set up before the move, and a skill you can't see is worse than a directory that isn't there. Antigravity has three official docs that disagree with each other, and the evidence that `~/.gemini/config/skills/` works across all three flavors is community testing, not official documentation.

The `PATHS_VERIFIED` date prints on every run so this is hard to forget. **Re-verify quarterly.** Paths live in the `GLOBAL_PATHS` dictionary at the top of `skill_audit.py`.

## Files

- `skill_audit.py` — the auditor, single file by design: static, offline, instant, no dependencies
- `test_skill_audit.py` — self-check, no framework: `python3 test_skill_audit.py`
- `route_check.py` — the routing harness: asks a real model which skill it would pick. Separate file on purpose; it needs the `claude` CLI and costs tokens.
- `test_route_check.py` — self-check for the harness's grading, model call stubbed: `python3 test_route_check.py`
- `cases/` — JSONL routing cases, one file per skill
- `docs/HAPPYPATH.md` — **start here**: the linear route from a pile of skill files to a `--strict`-clean library
- `docs/library-model.md` — **orientation first**: canonical copy, tool discovery, and POCKET/SHELF/UNKNOWN in one model
- `docs/living-manual.md` — detailed operational reference for discovery, modes, overlap heuristics, output, and the current skill map
- `docs/eli5/README.md` — kid-friendly guide to the personal skill library and audit
- `docs/eli5/skill-handbook.md` — kid-friendly usage guide for the current personal skills
- `docs/dos-and-donts.md` — finding-by-finding remediation guide mapping every finding code to actionable rules
- `docs/exemplars/skill-example.md` — one complete, verified-clean skill with the reasoning behind every line
- `docs/claude-project-skill-instructions.md` — paste-ready instructions for a Claude Project that writes skills for this library
- `docs/custom-openai-gpt-skill-instructions.md` — the same, for a Custom GPT (measured against the 8,000-character Instructions cap)
- `docs/custom-gemini-skill-instructions.md` — the same, for a Gemini Gem
- `docs/skill-wiki.md` — inventory, routing notes, and canonical-copy setup for installed skills
- `skill-setup.md` — per-tool reference: wiring each of the four cupboard tools and verifying they see your skills (Claude Desktop is not wired this way — see `docs/library-model.md`)
- `brief.md` — the build spec, including the YAML subset the hand-rolled frontmatter parser supports (plus multi-line plain scalars, which the spec omits but real skill files use)
