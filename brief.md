# Project Brief: `skill-audit`

A read-only command line tool that audits an agent skill library across Claude Code, Codex, Gemini CLI, and Antigravity on macOS.

Hand this file to Claude Code as the build spec.

---

## TL;DR

Build a Python script that finds every `SKILL.md` on the machine, checks it against a set of documented best practices, and prints a report. **It never modifies anything.** It only tells the user what to fix.

---

## Definitions

These three words are this tool's vocabulary, not vendor wording. Use them consistently in code, output, and JSON.

| Term | Meaning |
|---|---|
| **POCKET** | The agent can invoke it on its own. Its description sits in context every session. |
| **SHELF** | Explicit invocation only. The agent will not reach for it. |
| **UNKNOWN** | The tool has no documented flag for this, so the state cannot be determined. |

`UNKNOWN` is a real, expected state — not a failure. Gemini CLI and Antigravity currently have no documented way to block auto-invocation, so every skill visible only to those two reports as `UNKNOWN`.

Never guess a state. `UNKNOWN` is the correct answer when there is nothing to read.

---

## 1. Goal

One command answers four questions:

1. What skills do I actually have, and where?
2. Which ones are auto-invocable, explicit-only, or unknown, by tool?
3. Where am I over budget, duplicated, or overlapping?
4. What should my final stack look like?

---

## 2. Hard Constraints

These are not negotiable.

1. **Read-only.** The script never writes, moves, edits, or deletes a skill file. No auto-fix mode. Not even behind a flag.
2. **Python 3, standard library only.** No pip installs. It must run on a clean Mac with system Python.
3. **Single file.** One `skill_audit.py`. No package structure.
4. **No network calls.** Everything is local filesystem reads.
5. **Fails soft.** A missing directory, a broken symlink, or malformed YAML produces a warning line, not a crash.

---

## 3. Where To Look

Scan these locations. Skip any that do not exist and note it as "not present" rather than an error.

### Global scope

| Tool | Path |
|---|---|
| Claude Code | `~/.claude/skills/` |
| Codex + Gemini CLI | `~/.agents/skills/` |
| Gemini CLI (alt) | `~/.gemini/skills/` |
| Antigravity (all 3 flavors) | `~/.gemini/config/skills/` |

Also check these Antigravity paths and report them as **non-portable** if skills are found there, since only `~/.gemini/config/skills/` works across all three flavors:

- `~/.gemini/antigravity/skills/`
- `~/.gemini/antigravity-cli/skills/`

### Project scope

Accept an optional `--repo <path>` argument, repeatable. For each repo, scan:

- `<repo>/.claude/skills/`
- `<repo>/.agents/skills/`
- `<repo>/.gemini/skills/`

Also walk subdirectories for nested `.claude/skills/` and `.agents/skills/` folders. Report nested skills separately — they load differently and are a known source of surprise.

### Discovery rule

A skill is any directory containing a `SKILL.md`. Also accept a bare `SKILL.md` one level deep, since Gemini allows that layout.

---

## 4. Symlink Handling

This matters because the recommended setup is one source folder plus symlinks.

The script must:

1. **Resolve every path** to its real target.
2. **Deduplicate by real path.** If `~/.claude/skills/foo` and `~/.agents/skills/foo` resolve to the same place, that is one skill reachable from two cupboards. Report it as one entry with a list of reachable-from paths.
3. **Flag broken symlinks** by name and location.
4. **Flag the double-link problem.** If both `~/.gemini/skills/` and `~/.agents/skills/` resolve to the same target, warn. Gemini reads both as user scope, so the same skill lands in the same tier twice.
5. **Report cupboard coverage.** For each unique skill, say which of the four tools can currently see it.

---

## 5. Per-Skill Checks

For every skill found, parse the YAML frontmatter and run these checks.

### 5.1 Structure

- `SKILL.md` exists and is readable
- Frontmatter block is present and parses
- `description` field is present
- If `name` is present, does it match the directory name

### 5.1a Frontmatter parser scope

YAML parsing must use a small hand-rolled reader, not PyYAML, because of the stdlib-only rule.

**Support exactly these five forms. Nothing else.**

1. `key: value` — bare scalar
2. `key: "value"` or `key: 'value'` — quoted scalar
3. `key: [a, b, c]` — inline flow list
4. Block list — `key:` followed by indented `- item` lines
5. Block scalar — `key: |` or `key: >` followed by an indented block

Anything outside this set gets flagged as unparseable. Do not guess. Do not fall back to treating it as a string.

The parser reads only the block between the first `---` and the next `---` at the start of the file. If the file does not begin with `---`, there is no frontmatter.

**Reference block covering all five forms:**

```yaml
---
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
```

Booleans accept `true`, `false`, `yes`, `no`, `on`, `off`, `1`, and `0`, in any letter case. Treat anything else in a boolean field as unparseable.

### 5.1b Parse failure severity

Malformed frontmatter is **not always an error**. Severity depends on what was lost.

| Situation | Severity |
|---|---|
| No `---` block at all | `ERROR` — no metadata to check |
| Block present but `description` unreadable | `ERROR` — the trigger cannot be evaluated |
| Block present, `description` readable, one other field unparseable | `WARNING` — name the field, keep checking the rest |
| Unrecognized field name, but valid syntax | `NOTICE` — could be a newer feature, not a defect |

**The rule behind the table:** if the description survived, the skill is still auditable. Downgrade to a warning and keep going. Only escalate to error when the check itself becomes impossible.

Always print the field name and line number. "Malformed YAML" with no location is not actionable.

### 5.2 Description quality

The description is the trigger. Score it on:

- **Length.** Flag under 40 characters as too thin. Flag over 500 as bloated.
- **Missing trigger language.** Warn if it contains no "use when", "trigger", "when the user", or similar phrase.
- **Vague terms.** Flag descriptions containing only broad words like "helps with", "general", "various", "anything", "assists".
- **Front-loading.** Note if the first 100 characters do not contain a concrete noun for the job. This one is a soft hint, not a failure.

### 5.3 Body size

- Count lines in `SKILL.md`
- Flag over 500 lines with a recommendation to move detail into supporting files
- Report total character count for budget math

### 5.4 Invocation mode

Detect whether the skill is pocket or shelf.

Detect the invocation state **per tool**, not once per skill. The same skill can be `SHELF` in Claude and `UNKNOWN` in Gemini at the same time.

- **Claude:** `disable-model-invocation: true` in the `SKILL.md` frontmatter means `SHELF`. Absent means `POCKET`.
- **Codex:** `allow_implicit_invocation: false` under a `policy:` key means `SHELF`. Absent means `POCKET`.
- **Gemini CLI:** always `UNKNOWN`. No documented flag exists.
- **Antigravity:** always `UNKNOWN`. No documented flag exists.

**Where the Codex file lives.** It is per-skill, not global. The path is:

```
<skill-dir>/agents/openai.yaml
```

So for a skill at `~/.agents/skills/brand-voice/`, the file is `~/.agents/skills/brand-voice/agents/openai.yaml`. There is no repo-level or home-level version of this file. If it is absent, the default is `allow_implicit_invocation: true`, meaning pocket.

The relevant shape inside that file:

```yaml
policy:
  allow_implicit_invocation: false
```

Parse it with the same hand-rolled reader from 5.1a, extended to handle one level of nesting under `policy:`.

Report each skill's state for every tool that can currently see it. Flag any skill where two tools disagree — for example `SHELF` in Claude but `POCKET` in Codex. That is usually an oversight, not a decision.

Only `POCKET` skills count toward the budget math in 6.3 and the pocket check in 6.4. `UNKNOWN` skills are excluded from budget totals, and the report must say how many were excluded so the number is not mistaken for a complete picture.

---

## 6. Cross-Skill Checks

These are the ones that catch real problems.

### 6.1 Name collisions

Group skills by name. For each group with more than one member, report:

- Every location it appears in
- Which one wins, using the documented precedence per tool:
  - **Claude Code:** enterprise beats personal, personal beats project
  - **Gemini CLI:** workspace beats user beats extension beats built-in
  - **Codex:** does not resolve — both entries can appear in the picker
- Mark the Codex case as a warning, since there is no winner

Do not print a single "the winner is X" line. The winner differs per tool. Print a small table instead.

### 6.2 Overlap candidates

This is a heuristic, and the report must say so plainly.

**The algorithm, with real numbers:**

1. Lowercase each description and split on non-word characters
2. Drop tokens under 4 characters
3. Drop tokens in the stopword list (see below)
4. Deduplicate into a set per skill
5. For every pair of skills, compute the intersection

**Thresholds:**

| Shared distinctive terms | Severity |
|---|---|
| 0–2 | Ignore |
| 3–4 | `NOTICE` — probably fine |
| 5 or more | `WARNING` — read both files |
| Any shared quoted trigger phrase | `WARNING` regardless of term count |

Bump any `NOTICE` to `WARNING` when neither skill in the pair is the declared owner of a job area in the config file (section 7).

**Stopword list.** Include at minimum: `when`, `user`, `asks`, `use`, `this`, `that`, `with`, `from`, `should`, `would`, `will`, `trigger`, `triggers`, `skill`, `used`, `using`, `about`, `into`, `also`, `like`, `such`, `their`, `they`, `them`, `have`, `been`, `more`, `most`, `then`, `than`, `these`, `those`, `what`, `which`, `does`, `create`, `generate`, `write`, `make`, `help`, `content`. Keep it as an editable constant at the top of the file.

Output as "these two may overlap — read them" not "these conflict."

### 6.3 Budget estimates

Two separate budgets, because the tools differ.

**Claude Code:** the skill listing budget scales at roughly 1% of the model context window, and individual entries are capped around 1,536 characters. Sum the name plus description characters for all pocket skills. Report the total and flag entries over the per-entry cap.

**Codex:** the initial skill list uses at most 2% of the context window, or 8,000 characters when the window size is unknown. Use 8,000 as the conservative default. Sum pocket skill name plus description characters. Flag if over.

Make the assumed context window size a constant at the top of the file with a comment, so it is easy to adjust.

### 6.4 Pocket count

Read an optional config file (see section 7). Compare the intended pocket list against what is actually pocket on disk. Report three lists:

- Intended pocket, and actually pocket — correct
- Intended shelf, but actually pocket — needs a flag added
- Intended pocket, but actually shelf — flag added by mistake

If no config file exists, just report the pocket count and warn if it exceeds five.

---

## 7. Config File

Optional. Path: `~/.skill-audit.toml`, or `--config <path>`.

Parse with the stdlib `tomllib` module. If the file is missing, run with defaults and say so.

```toml
[pocket]
skills = ["startday", "session-handoff", "past-chat-archaeologist", "bandwidth-snapshot", "brand-voice"]

[ownership]
# Declares which skill owns a job area. Used to flag unclaimed overlap.
"morning brief" = "startday"
"bandwidth method" = "bandwidth-snapshot"
"public content" = "brand-voice"

[budget]
context_window = 200000
```

If two skills overlap and neither is the declared owner of any area, raise the severity of that overlap warning.

---

## 8a. Terminal Output Format

Plain text. No color codes unless stdout is a TTY. Sections in this order:

1. **Summary** — total skills, unique skills, pocket count, locations scanned
2. **Inventory** — table of name, real path, reachable-from tools, pocket/shelf, line count
3. **Errors** — unparseable frontmatter, broken symlinks, missing descriptions
4. **Warnings** — weak descriptions, oversized bodies, non-portable Antigravity paths, double links
5. **Name collisions** — with the per-tool precedence table
6. **Overlap candidates** — clearly labeled as a hint requiring human review
7. **Budget** — Claude and Codex figures, with pass or over
8. **Pocket check** — intended versus actual
9. **Recommended actions** — a numbered list, ordered by severity

Each section prints even when empty, with a one-line "none found" note. A section that silently vanishes looks like a bug.

---

## 8b. CLI Flags

| Flag | Effect |
|---|---|
| `--repo <path>` | Add a repo to scan. Repeatable. |
| `--config <path>` | Use a specific config file |
| `--json` | Emit the full report as JSON instead of text |
| `--markdown <path>` | Also write a markdown version of the report to that path |
| `--quiet` | Print errors and warnings only. Skip inventory, budget, and pocket check. |
| `--tool <name>` | Limit the scan to one tool: claude, codex, gemini, antigravity |
| `--strict` | Treat warnings as failures. See exit codes. |
| `--version` | Print version and the `PATHS_VERIFIED` date |

**Flag interactions:**

- `--json` overrides `--quiet`. JSON is always the full structure, since a consumer filters it themselves.
- `--markdown` always writes the full report, regardless of `--quiet`. Quiet controls the terminal only.

### JSON scope

`--json` emits **everything** — raw findings, severity levels, and derived recommendations. Nothing is text-only.

Top-level keys:

```
meta          — version, paths_verified date, scan timestamp, locations scanned
skills        — array of every unique skill, with per-tool state
findings      — array of every finding
collisions    — name collision groups with per-tool precedence
overlaps      — candidate pairs with shared term counts
budget        — claude and codex figures, plus excluded UNKNOWN count
pocket_check  — intended vs actual
recommendations — ordered array, same content as section 9 of the text report
```

Every entry in `findings` carries: `severity` (one of `error`, `warning`, `notice`), `code` (a short stable string like `weak_description`), `skill`, `path`, and `message`.

**Stable codes matter.** A consumer should be able to filter on `code` without string-matching the human message. Keep the code list as a constant at the top of the file.

---

## 8c. Exit Codes

| Code | Meaning |
|---|---|
| `0` | Clean, or warnings only in default mode |
| `1` | Warnings found, and `--strict` was passed |
| `2` | Errors found |
| `3` | Script failure |

**The important rule:** warnings alone do **not** fail the run by default. Exit `0`.

This is deliberate. Warnings are advisory — a thin description or a possible overlap is something to read, not something that should break a pipeline. If you want warnings to fail, pass `--strict`.

`--quiet` changes what prints. It never changes the exit code. Suppressing output and suppressing status are different jobs, and mixing them makes the tool unpredictable.

State all of this in `--help`.

---

## 9. Non-Goals

State these in the script's own `--help` text so nobody expects them.

1. **It does not detect real conflicts.** Two skills can give opposite instructions in plain prose that share no keywords. The overlap check is a word-similarity hint. A human still has to read the files.
2. **It does not fix anything.**
3. **It does not verify triggering.** Whether a skill actually fires on a given prompt requires running the agent. That is an eval, not an audit.
4. **It does not check Gemini or Antigravity shelf state.** No documented flag exists for either. Report those skills as "invocation mode unknown."

---

## 10. Acceptance Criteria

The build is done when all of these pass.

1. Runs on a Mac with system Python 3 and no installs
2. Handles a machine with zero skills without crashing
3. Handles a machine where all four global paths symlink to one folder, and reports each skill once
4. Correctly identifies a skill with `disable-model-invocation: true` as shelf
5. Correctly flags a `SKILL.md` with no frontmatter
6. Correctly flags a broken symlink without stopping the scan
7. Produces valid JSON with `--json`
8. Never writes to any path outside the one given by `--markdown`
9. `--help` states the four non-goals
10. Parses all five YAML forms in the 5.1a reference block, and flags a sixth form it does not recognize
11. Reads `<skill-dir>/agents/openai.yaml` and reports the skill as shelf when `allow_implicit_invocation: false`
12. Two descriptions sharing 5+ distinctive terms produce a `WARNING`; two sharing 2 produce nothing
13. A run with warnings and no errors exits `0` by default, and exits `1` with `--strict`
14. `--quiet` changes printed output but produces the same exit code as a normal run
15. A skill visible only to Gemini reports `UNKNOWN`, not `POCKET`, and is excluded from budget totals
16. A `SKILL.md` with a readable description but one broken field produces a `WARNING`, not an `ERROR`, and names the field and line
17. `--json` output includes `recommendations` and a `severity` plus stable `code` on every finding

---

## 11. Build Notes

- Write the checks as small independent functions so new ones are easy to add later
- Keep the tool-specific paths in a single dictionary constant at the top, since these paths have changed within the past year and will change again
- Add a comment above that dictionary with the date the paths were verified: **August 1, 2026**
- Include a `--version` flag and a `PATHS_VERIFIED` constant so it is obvious when the path data is stale
- Prefer readable output over dense output. This report gets read by a human who is deciding what to delete.

---

## 12. Known Path Instability

Tell the user this in the report footer.

These paths moved recently. Codex changed from `~/.codex/skills` to `.agents/skills`. Antigravity has three official docs that disagree with each other, and `~/.gemini/config/skills/` is the only global path confirmed to work across all three of its flavors — that finding is community testing, not official documentation.

**Re-verify quarterly.** The script should print the `PATHS_VERIFIED` date every run so this is impossible to forget.