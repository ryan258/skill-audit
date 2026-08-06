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

Python 3, standard library only. No installs, no network calls. `tomllib` (3.11+) is used for the audit config when available; on older Pythons a small fallback handles the documented audit shape, and a separate narrow reader handles Codex `[[skills.config]]` entries.

## Vocabulary

The report uses four words consistently. They're this tool's terms, not vendor wording.

| Term | Meaning |
|---|---|
| **POCKET** | The agent can invoke it on its own. Its effective listing metadata sits in context every session (normally name plus description; Claude `name-only` carries just the name). |
| **SHELF** | Explicit invocation only. The agent won't reach for it. |
| **UNKNOWN** | The tool has no documented flag for this, so the state can't be determined. |
| **DISABLED** | The host explicitly hides or disables this skill; it is not invocable there. |

`UNKNOWN` is an expected state, not a failure. Antigravity has no readable per-skill invocation setting, and malformed or unreadable host configuration is never guessed. Gemini CLI is different: the audit reads its persistent `skills.enabled` and union-merged `skills.disabled` settings, so a valid Gemini configuration reports `POCKET` or `DISABLED`.

## What it checks

**Per skill** — frontmatter parses; portable name, description, compatibility, and metadata limits; `name` matches the directory; description length, trigger language, vagueness, front-loading; body over 500 lines; invocation state *per tool*. Claude combines `disable-model-invocation` with `~/.claude/settings.json` `skillOverrides`; Codex combines `agents/openai.yaml` → `policy.allow_implicit_invocation` with `~/.codex/config.toml` `[[skills.config]] enabled`; Gemini merges persistent system, user, and explicitly audited workspace settings, including `skills.enabled` and `skills.disabled`. An explicit host-off setting reports `DISABLED` and overrides file-local routing metadata.

**Claude Desktop** is scanned as a *separate library* — vendor-documented behavior: Cowork and cloud sessions do not read `~/.claude/skills/`, they load the skills enabled for your claude.ai account. Its skills sync from your account (including Anthropic's own built-ins), cached under two app-assigned identifiers, and its invocation mode comes from that cache's `manifest.json` `enabled` flag rather than `disable-model-invocation`. Because that library never shares a listing with your local one, name collisions and overlap are scoped per library — a skill present in both is two libraries agreeing, not a conflict. Its listing size is reported but not graded: no published budget exists, and inventing one would manufacture a verdict the vendor never stated.

**Across skills** — name collisions (every location, plus which copy actually wins under each tool's documented precedence, plus Gemini's within-tier preference for `.agents/skills` over `.gemini/skills` — observed, not vendor-documented: re-checked 2026-08-06, the Gemini docs call the two "aliases" and state no within-tier order, but `gemini skills list --all` prints which path overrides which), description overlap candidates, reciprocal named handoffs (kept visible as non-blocking notices), trigger-phrase containment (one quoted trigger is a whole-word slice of another — a hint that the pair competes, not proof that either is unreachable; which one gets picked is the model's call), dangling `skills/<name>/SKILL.md` references to skills that aren't installed, context-budget math, and intended-vs-actual pocket count.

Budgets are counted **per tool**: a skill shelved in Claude but pocket in Codex or Gemini costs only the listings where it is pocket. Claude and Codex are graded against documented/conservative limits; Gemini and Claude Desktop totals are counted but not graded because no published limit exists. The pocket check is deliberately broader — a skill counts as pocket if *any* tool that can see it will auto-invoke it — so the numbers can legitimately disagree. Every section prints the rule it used.

The pocket check compares **global-scope skills only** against your config. A repo's own skills aren't governed by a global pocket list, so they're counted and listed separately rather than reported as drift. The same applies to Claude Desktop: that library's on/off switch lives in the app, not in this config, so its pocket skills print under their own heading and are never called drift — a comparison you could not act on isn't a finding.

With `--tool`, config checks are scoped to what the selected tools can establish.
An installed skill whose selected-tool mode is `UNKNOWN` or non-pocket, or a
configured name visible only to an excluded tool, is listed informationally and
never misreported as globally SHELF or missing—the excluded host may satisfy the
config's any-tool POCKET rule. An observed selected-tool POCKET state still
proves pocket status. Unmatched overlap suppressions are likewise judged only on
an unfiltered library scan.

The count itself is by **distinct name**. A skill synced to both your local library and Desktop is one skill in two places, so it counts once.

**Vendor-installed skills** — Anthropic's Desktop built-ins and Codex's bundled `.system` skills — have their quality findings demoted to `notice` and tagged `[vendor-installed]`. You can't edit them, so they must never fail `--strict`. They are still counted and listed: their descriptions consume the same listing budget as yours.

**Symlinks** — every path is resolved and deduplicated by real target, so one folder reachable from four cupboards reports as one skill with a list of reachable-from paths. Broken symlinks are named and skipped, not fatal. If `~/.gemini/skills` and `~/.agents/skills` resolve to the same target, you get a double-link warning.

## Where it looks

Global (skipped quietly and marked "not present" if absent):

| Tool | Path |
|---|---|
| [Claude Code](https://code.claude.com/docs/en/slash-commands) | `~/.claude/skills/` |
| [Codex](https://developers.openai.com/codex/skills) + [Gemini CLI](https://geminicli.com/docs/cli/using-agent-skills/) | `~/.agents/skills/` |
| [Codex](https://developers.openai.com/codex/skills) (legacy) | `~/.codex/skills/` — still scanned; holds the installs on any machine set up before the move |
| [Codex](https://developers.openai.com/codex/skills) (system) | `/etc/codex/skills/` — the documented admin location |
| [Gemini CLI](https://geminicli.com/docs/cli/using-agent-skills/) (alt) | `~/.gemini/skills/` |
| [Antigravity](https://antigravity.google/docs/skills) | `~/.gemini/config/skills/` — documented global path |
| Claude Desktop | `~/Library/Application Support/Claude/local-agent-mode-sessions/skills-plugin/*/*/skills` — macOS, globbed; a separate account-synced library |

`~/.gemini/antigravity/skills/` and `~/.gemini/antigravity-cli/skills/` are also scanned and flagged **non-portable** so older installs do not disappear from the inventory.

Project scope via `--repo`: `.claude/skills/`; `.agents/skills/` for Codex, Gemini, and Antigravity; `.gemini/skills/` for Gemini; and Antigravity's backward-compatible `.agent/skills/`, plus nested copies deeper in the tree, reported separately since they load differently.

An explicitly supplied `--repo` is treated as the workspace context being
audited. The scanner does not model Gemini's interactive folder-trust decision;
if Gemini reports that a folder is untrusted, its workspace skills, settings,
and hooks remain skipped even though the audit can inspect the files.

A skill is any directory containing a `SKILL.md`.

## Flags

| Flag | Effect |
|---|---|
| `--repo PATH` | Add a repo to scan. Repeatable; the repo is treated as the audited workspace context, not proof of host folder trust. |
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

Cases are JSONL — `{"query": "...", "expected": "skill-name"}`, or `"expected": null` for "no skill should fire". Routing is classification, so grading is string equality: no second model judging prose, nothing to calibrate. Only POCKET skills are offered; SHELF, DISABLED, UNKNOWN, and absent skills are outside the listing and cannot be routed to. A case expecting one is reported as `SKIP`, costs no model calls, and doesn't count toward the pass rate or the exit code — the sample file above ships with three such cases, since `dhp-context-sync` is shelved.

`--repeat N` runs each case N times and reports a rate. Routing is non-deterministic, and a skill that wins 2 times in 3 is the finding. `--model` picks the alias passed to `claude --model` (default `sonnet`); `--jobs` sets how many calls run in parallel (default 8). Both reject values below 1.

It shells out to `claude -p` with `--system-prompt`, so it needs the CLI on PATH, costs tokens, and takes seconds per call. That is why it is a separate file: the auditor stays offline, instant, and dependency-free.

`route_check.py` returns exit 3 when any model call times out, the CLI fails, or it returns an empty response. Those are harness failures, not routing misses: the affected case has `rate: null`, its error responses are retained under `errors`, and it is excluded from the completed-case score. Exit 1 is reserved for completed calls that selected the wrong skill.

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

Top-level keys: `meta`, `skills`, `findings`, `collisions`, `overlaps`, `dangling_references`, `budget`, `pocket_check`, `recommendations`. Every skill includes per-tool `states`, effective `listing_descriptions`, and any `host_overrides`. Every finding carries `severity` (`error`/`warning`/`notice`), a stable `code`, `skill`, `path`, and `message` — filter on `code`, not the human text. The code list is a constant at the top of `skill_audit.py`.

## Sample

```text
skill-audit 1.2.0 | paths verified 2026-08-06

Summary
-------
26 unique skills; 17 pocket in at least one tool; 26 discovered entries; 7 locations scanned
config: not present; using defaults
present: /Users/you/.claude/skills
not present: /Users/you/.agents/skills

Errors
------
[unparseable_field] Unparseable field 'description' — a plain scalar cannot contain ': '
  or ' #'; wrap the value in quotes (line 3) — /Users/you/.skills/broken-example

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
Gemini: 1180 chars across 4 enabled skills (not measured — no published limit)
Desktop: 7405 chars across 20 enabled skills (not measured — no published limit)
0 skills excluded: only Antigravity can see them, and its mode is UNKNOWN
```

Every section prints even when empty, with a "none found" note. A section that silently vanishes looks like a bug.

## Non-goals

1. **It doesn't detect real conflicts.** Two skills can give opposite instructions in prose that shares no keywords. The overlap check is a word-similarity hint — a human still reads the files.
2. **It doesn't fix anything.** No auto-fix mode, not even behind a flag.
3. **It doesn't verify triggering.** Whether a skill fires on a given prompt requires running the agent. That's an eval, not an audit — see `route_check.py` below, which is that eval and is deliberately a separate tool.
4. **It doesn't guess Antigravity shelf state.** No readable per-skill signal exists there. Gemini's persistent enabled/disabled settings are modeled, but its disable control is not an explicit-invocation shelf.

## Path instability

These paths moved recently. Codex changed from `~/.codex/skills` to `.agents/skills` — both are scanned, because the old location still holds installs on machines set up before the move. Antigravity currently documents `~/.gemini/config/skills/` globally and `.agents/skills/` in a workspace, with backward support for `.agent/skills/`; the older global `antigravity` and `antigravity-cli` roots remain visible as non-portable evidence.

The `PATHS_VERIFIED` date prints on every run so this is hard to forget. **Re-verify quarterly.** Paths live in the `GLOBAL_PATHS` dictionary at the top of `skill_audit.py`.

## Files

- `skill_audit.py` — the auditor, single file by design: static, offline, instant, no dependencies
- `test_skill_audit.py` — self-check, no framework: `python3 test_skill_audit.py`
- `route_check.py` — the routing harness: asks a real model which skill it would pick. Separate file on purpose; it needs the `claude` CLI and costs tokens.
- `test_route_check.py` — self-check for the harness's grading, model call stubbed: `python3 test_route_check.py`
- `cases/` — JSONL routing cases, one file per skill
- [docs/skill-best-practices.md](docs/skill-best-practices.md) — standalone standard for translating raw instructions into reviewable, portable skill bundles and safely installing them under `~/.skills`
- `docs/HAPPYPATH.md` — **start here**: the linear route from a pile of skill files to a `--strict`-clean library
- `docs/library-model.md` — **orientation first**: canonical copy, tool discovery, and POCKET/SHELF/UNKNOWN/DISABLED in one model
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
