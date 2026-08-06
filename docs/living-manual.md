# skill-audit living manual

New to this library? Start with [The skill-library model](library-model.md) for
the orientation; this manual is the detailed audit and operations reference.

> **Implementation status:** this manual describes version 1.2.0 of
> `skill_audit.py`, as it exists in this repository. It is an operational
> reference, not a promise that a vendor will keep the same filesystem paths or
> invocation behavior. Check `PATHS_VERIFIED` with `--version` and re-verify the
> vendor-dependent parts quarterly.

## Start here

`skill-audit` is a standard-library Python CLI for inspecting local `SKILL.md`
libraries across Claude Code, Codex, Gemini CLI, and Antigravity. It answers
four practical questions:

1. Which skill directories are actually discoverable from the configured
   locations?
2. Are their descriptions and frontmatter usable as routing metadata?
3. Which skills are auto-invocable, explicit-only, explicitly disabled, or
   honestly unknown for each tool?
4. Where are duplicate names, similar descriptions, budget pressure, or drift
   from the library owner’s stated intent?

The tool is designed to be safe to run against a real home directory:

- It does not change a skill file, a symlink, or a configuration file.
- It makes no network calls and has no third-party dependencies.
- Its only write is an explicitly requested `--markdown PATH` report.
- It reports uncertainty instead of inventing an answer, especially for
  undocumented tool behavior.

The key boundary is important: this is a **static audit**. It establishes that
a skill is reachable and its metadata is inspectable. It cannot prove that a
particular agent will select a skill for a particular prompt. That requires a
fresh-session behavioral evaluation in the target tool.

## Quick operating loop

```sh
# Inspect the global skill library.
python3 skill_audit.py

# Inspect the global library plus a repository's project and nested skills.
python3 skill_audit.py --repo /path/to/repository

# Make warnings fail a CI check.
python3 skill_audit.py --strict

# Save a human-readable snapshot while retaining normal terminal output.
python3 skill_audit.py --markdown audit-report.md

# Consume the full structured report in another program.
python3 skill_audit.py --json
```

For normal maintenance, run the strict form after changing a skill description,
its invocation settings, or its links. For a new pocket skill, also run one
live triggering evaluation before deciding the library is healthy.

## Terms used by this project

These terms are audit vocabulary. They are not intended to replace any vendor’s
own terminology.

| Term | Meaning | Why it matters |
|---|---|---|
| **POCKET** | The tool can invoke the skill without the user naming it. | Its effective listing text consumes always-present context; Claude `name-only` is the name without the description. |
| **SHELF** | The skill is explicit-only for that tool. | It remains available, but does not compete for automatic selection. |
| **UNKNOWN** | The audit has no readable, valid setting it can use to infer the mode. | The audit neither calls it pocket nor shelf, and does not count it in a known budget. |
| **DISABLED** | The host explicitly hides or disables the skill. | It is not invocable or counted in that host's listing budget. |
| **Global** | A skill found in a user-level tool directory. | It participates in the optional global pocket-intent comparison. |
| **Project** | A skill found directly under a selected repository’s skill directory. | It is counted and reported, but is not compared against the global pocket list. |
| **Nested** | A skill directory found deeper inside a selected repository. | It is reported separately because its loading and precedence can differ. |
| **Real path** | The resolved filesystem target of a skill directory. | This is how the audit distinguishes one linked skill from two copied skills. |

## What counts as a skill

A skill is any directory that contains a file named `SKILL.md`. The scanner
walks below each configured root, so grouped directories are supported. It does
not follow symlinked directories while walking, but it does recognize a symlink
directory that itself contains `SKILL.md`; this preserves the recommended
one-canonical-copy setup.

The scanner reports dangling links instead of crashing. It also finds dangling
links below the root, not only at the root’s first level.

## Discovery: where the tool looks

The global locations are intentionally explicit in the `GLOBAL_PATHS` constant.
Missing locations are reported as `not present`, not errors.

| Tool | Global locations scanned | Invocation state the audit can establish |
|---|---|---|
| Claude Code | `~/.claude/skills/` | POCKET, SHELF, or DISABLED |
| Codex | `~/.agents/skills/`, plus legacy `~/.codex/skills/` and system `/etc/codex/skills/` | POCKET, SHELF, or DISABLED |
| Gemini CLI | `~/.agents/skills/`, `~/.gemini/skills/` | POCKET or DISABLED; UNKNOWN only when persistent settings are invalid or unreadable |
| Antigravity | documented `~/.gemini/config/skills/` | UNKNOWN |
| Claude Desktop | `~/Library/Application Support/Claude/local-agent-mode-sessions/skills-plugin/*/*/skills` (macOS, globbed) | POCKET or SHELF, from the cache manifest's `enabled` flag |

The scanner also checks the older global
`~/.gemini/antigravity/skills/` and
`~/.gemini/antigravity-cli/skills/` roots. If either contains skills, they are
included but the audit emits `non_portable_path`.

### Project scans

Each `--repo PATH` may be supplied more than once. For every existing repository
path, the tool considers these direct directories:

```text
.claude/skills/   -> Claude
.agents/skills/   -> Codex, Gemini, and Antigravity
.gemini/skills/   -> Gemini
.agent/skills/    -> Antigravity backward compatibility
```

It also searches for nested copies of those directories. The recursive search
prunes `.git`, `node_modules`, virtual environments, caches, build output, and
common package/build directories so a large repository is not needlessly walked.
A missing `--repo` produces an `unreadable` warning and does not stop the rest
of the scan.

Passing `--repo` says "audit this workspace"; it does not prove that a host has
trusted the folder. In particular, Gemini can skip project agents, workspace
settings, and hooks until its own folder-trust check succeeds. The audit treats
an explicitly supplied repository as the settings context and leaves that
interactive trust decision to the host.

### Links, aliases, and copies

The audit groups discovered entries by resolved real path. One physical skill
linked into several agent directories therefore becomes one inventory item with
multiple `reachable_from` locations. That is the intended result.

Two physical directories with the same skill name remain separate inventory
items. They produce a `name_collision`, because they can drift even if their
initial content happens to match.

The scanner additionally detects Gemini’s double-link situation: when
`~/.agents/skills` and `~/.gemini/skills` resolve to the same directory, Gemini
can see the same user-scope library through both roots. The audit emits one
`double_link` warning for the root-level configuration.

Broken-link findings are deduplicated by the link entry’s filesystem identity,
not merely by the missing target. This means one dead link reachable through
two aliases is one cleanup, while two distinct dead links aimed at the same
missing directory are two cleanups.

## Skill metadata: the supported YAML subset

The parser deliberately accepts a small, conservative YAML subset. It does not
depend on a YAML package and does not guess at forms it cannot safely parse.
Unparseable metadata is surfaced before downstream checks use it.

Supported forms are:

- plain scalars;
- quoted scalars;
- flow lists, including quoted commas;
- block lists;
- literal (`|`) and folded (`>`) block scalars;
- multi-line plain scalars, folded with spaces; and
- a string-to-string `metadata` mapping in `SKILL.md`; and
- one level of mappings in Codex’s `agents/openai.yaml`.

Unsupported forms include anchors, aliases, tags, inline flow mappings, and
other YAML constructs outside that subset. The audit reports
`unparseable_field` rather than pretending it understood them.

### Plain-scalar trap

Within this parser, an unquoted scalar cannot contain `: ` or ` #`, because
those sequences have YAML structural meaning. Quote such a value:

```yaml
# Bad: parsed as malformed.
description: Runs a release review: security, rollout, rollback

# Good.
description: "Runs a release review: security, rollout, rollback"

# Also good: a bare # in C# is not a comment delimiter.
description: Refactors C# code. Use when the user asks for a safe cleanup.
```

### Recognized `SKILL.md` fields

The recognized fields are `name`, `description`, `allowed-tools`,
`disable-model-invocation`, `paths`, `when_to_use`, `license`, `metadata`,
`compatibility`, and `argument-hint`.

An unfamiliar but syntactically readable field is a `unknown_field` notice, not
an error: a vendor may have added it. The audit’s important requirement is that
the fields it relies on are readable.

Portable structural validation follows the Agent Skills limits: a present name
must use 1–64 lowercase letters, digits, and single hyphens; a description may
not exceed 1,024 characters; `compatibility`, when present, is a non-empty
string of at most 500 characters; and `metadata`, when present, maps strings to
strings. Violations are errors. The tighter 40–500 description range remains an
advisory routing-quality check inside that portable envelope.

## Description quality and routing contract

The description is the skill’s routing contract. An agent can make its initial
selection from the visible name and description; a sophisticated body cannot
rescue a description that is too vague to select.

For every usable description, the audit checks:

| Check | Current rule | Finding if it fails |
|---|---|---|
| Presence | A non-empty string must be readable. | `missing_description` (error) |
| Portable maximum | No more than 1,024 characters. | `invalid_description` (error) |
| Quality length | At least 40 and no more than 500 characters. | `thin_description` / `bloated_description` |
| Trigger language | Must use one of the recognized routing patterns. | `missing_trigger` |
| Vague-only text | After stopword removal, remaining words must not be only vague terms. | `vague_description` |
| Early signal | The first 100 characters should contain a distinctive non-vague term. | `late_job_noun` (notice) |
| Body size | `SKILL.md` must not exceed 500 lines. | `oversized_body` |
| Claude entry cap | For a Claude POCKET entry, its effective listing name plus description must not exceed 1,536 characters. | `entry_cap_exceeded` |

Recognized trigger language includes:

- `use when`;
- `use before` or `use after`;
- `use at the start of` or `use at the end of`;
- `trigger` or `triggers`;
- `when user` or `when the user`; and
- `for … request` or `for … requests`.

`use as` is intentionally not accepted. It commonly occurs in ordinary prose
and would create false confidence that a description has clear routing guidance.

The early-signal check is intentionally simpler than grammatical part-of-speech
analysis: it looks for distinctive tokens after removing stopwords and vague
words. It does not claim to identify a literal noun.

## The two libraries

The tool scans two libraries that never meet. The **local** one is the
filesystem cupboards (`.claude`, `.agents`, `.agent`, `.gemini`, `.codex`). The
**claude-desktop** one is the account-synced set the desktop app caches under
two identifiers it assigns, so its configured location contains `*` segments
and is expanded by glob; a pattern matching nothing is still listed as *not
present*, because a location that silently disappears from the summary is the
failure this tool exists to prevent.

Every comparison between skills is scoped to one library. A name in both is
one skill synced two ways, not a collision, and no documented precedence rule
relates them because they are never offered to the same model at once. On the
same name can appear in both libraries and still produce zero collisions;
without the scoping those would be false conflicts.

Desktop invocation mode is read from the cache's `manifest.json` `enabled`
flag — Desktop's equivalent of `disable-model-invocation`. A skill absent from
the manifest, or an unreadable manifest, yields UNKNOWN rather than an assumed
POCKET. That path is one machine's observation, not vendor documentation.

## Per-tool invocation mode

The same physical skill can be visible to several tools and have a different
mode in each. The audit models mode per tool instead of assigning one mode to
the directory.

| Tool | File-local SHELF signal | Host override | Default when visible |
|---|---|---|---|
| Claude Code | `disable-model-invocation: true` in the skill frontmatter | `~/.claude/settings.json` `skillOverrides`: `on`, `name-only`, `user-invocable-only`, or `off` | POCKET |
| Codex | `policy.allow_implicit_invocation: false` in `<skill>/agents/openai.yaml` | `~/.codex/config.toml` `[[skills.config]] enabled = false` | POCKET |
| Gemini CLI | No explicit-only shelf | Persistent `skills.enabled`, `admin.skills.enabled`, and union-merged `skills.disabled` | POCKET |
| Antigravity | No documented shelf signal used here | None modeled | UNKNOWN |

Codex policy files normally do not have `---` delimiters. The parser supports
them as a synthetic frontmatter block and handles sibling mappings such as
`interface:` and `policy:`. A sibling mapping does not alter invocation mode;
only `policy.allow_implicit_invocation` does.

Host settings take precedence over file-local routing metadata. Claude maps
`off` to DISABLED, `user-invocable-only` to SHELF, and `on` or `name-only` to
POCKET; `name-only` contributes only the name to budget math. Codex
`enabled = false` maps to DISABLED. Gemini reads persistent system defaults,
user settings, the explicitly audited workspace settings, and the system
override in vendor precedence order; disabled-name arrays union across layers.
A malformed layer emits `config_error` and yields UNKNOWN instead of a guess.
DISABLED is not treated as a POCKET/SHELF mode disagreement because the host has
removed the skill from invocation.

If Claude and Codex can both see a skill and one resolves to POCKET while the
other resolves to SHELF, the audit emits `mode_disagreement`. That is normally a
half-finished configuration change, so it is a warning rather than silent
metadata. Gemini is excluded because it exposes no SHELF choice to agree with.

## Budget model

Budget calculations are separate per host. Only Claude and Codex have graded
limits; Gemini and Claude Desktop are counted but marked not measured.

| Tool | Calculation | Default limit |
|---|---|---|
| Claude | Sum the effective listing text for Claude POCKET skills (`name + description`, or only `name` under `name-only`). | 1% of context window; 2,000 characters with the default 200,000 window. |
| Codex | Sum the same values for Codex-visible POCKET skills. | 2% of context window, capped at 8,000 characters; 4,000 with the default window. |
| Gemini | Sum `name + description` for Gemini POCKET skills. | None published; total is reported without a verdict. |
| Claude Desktop | Sum `name + description` for manifest-enabled skills. | None published; total is reported without a verdict. |

Configure another assumed context window when appropriate:

```toml
[budget]
context_window = 200000
```

A skill shelved in Claude but pocket in Codex or Gemini costs only the listings
where it is pocket. A skill visible only to Antigravity is counted in the
inventory but excluded from known totals because its state is UNKNOWN. The
report prints the number excluded so a low total cannot be mistaken for full
coverage.

The separate **pocket check** uses a deliberately broader rule: a skill counts
as pocket if any visible tool marks it POCKET. This can legitimately differ from
either per-tool budget total. The count is by distinct name across every
library, so a skill synced to both the local library and Claude Desktop counts
once rather than twice.

## Pocket intent and configuration

The optional configuration path defaults to `~/.skill-audit.toml`. Python 3.11+
uses `tomllib`; older Python versions use a small fallback parser for this
documented configuration shape.

```toml
[pocket]
skills = ["startday", "session-handoff", "brand-voice"]

[ownership]
"morning brief" = "startday"
"public content" = "brand-voice"

[overlap]
# Mutes overlap pairs you have read and judged benign. Entries are pair labels
# split on " / ", exactly as the report prints them, or a bare skill name to
# mute every pair that skill appears in. An entry matching nothing warns.
suppress = ["idea-refine / interview-me", "interview-me / grill-me"]

[budget]
context_window = 200000
```

A missing configuration file is normal and the audit says so. A file that parses
but holds a wrongly-shaped value — a scalar where a list belongs, a string
`context_window` — has that value ignored with a `config_error` warning, and the
rest of the run continues on defaults. Configuration is never a reason for a
read-only audit to abort. Sections the tool does not document are left alone
rather than reported.

The pocket list is an intent record for global-scope skills. With no list, the
audit only counts POCKET skills and warns when the total exceeds five. With a
list, it compares installed global skills against intent:

| Result | Meaning | Finding |
|---|---|---|
| Correct | Listed in config and actually POCKET. | None |
| Intended shelf but pocket | An installed global skill is POCKET but absent from the list. | `intended_shelf_pocket` |
| Intended pocket but shelf/disabled | A listed installed skill has a known non-POCKET state. | `intended_pocket_shelf` |
| Installed, mode unknown | A listed skill exists, but every selected tool reports UNKNOWN. | Informational `intended_mode_unknown`; no finding |
| Selected tools non-pocket | Under `--tool`, a listed skill is SHELF or DISABLED, but an excluded host may still satisfy the any-tool intent. | Informational `intended_selected_nonpocket`; no finding |
| Not visible under `--tool` | A configured name may exist only in an excluded tool. | Informational `intended_not_visible`; no finding |
| Intended but not installed | The list names no discovered skill. | `intended_missing` |

Project and nested skills still contribute to the total pocket count, but are
listed separately and never declared drift from a user-global configuration.
If duplicate copies share a name, their scopes are unioned before this decision,
so a global copy cannot accidentally disappear behind a project copy.

Claude Desktop's library is treated the same way, for a different reason: this
configuration file cannot switch a Desktop skill off — that control lives in the
app — so measuring one against the list would report drift no edit could ever
resolve. Its pocket skills are counted and printed under `desktop_pocket`, and
the config comparison covers the local libraries only. A name is judged against
the list when a *local* copy is POCKET, so a skill correctly shelved locally is
not reported as drift merely because the Desktop copy is enabled.

## Vendor-installed skills

Some skills arrive already written: Anthropic's built-ins in the Claude Desktop
library, and the skills Codex bundles under a `.system` directory in its skills
tree. You did not author them and cannot edit them.

Their findings are still produced — the audit does not hide them, because a
vendor's effective listing metadata consumes listing budget just like your own, and a
budget that quietly omitted them would understate the real cost. But quality
findings against them are demoted from `warning` to `notice` and their message
gains a `[vendor-installed]` suffix naming the reason. A `--strict` run must
never fail on wording you have no power to change.

The demotion covers description quality, overlap, intent shadowing, unknown
fields, and unparseable frontmatter fields.
Overlap *pairs* are demoted alongside the matching finding when both skills are
vendor-installed, so a consumer filtering on `overlaps[].severity` cannot
disagree with the findings list about the same pair. A pair with one vendor
skill and one of yours keeps its original severity: that one you can act on, by
changing your own side.

Detection is by library for Desktop, and by a `.system` path segment for Codex,
so a Codex install that keeps its skills somewhere other than `~/.codex/skills/`
is still recognized.

## Name collisions and precedence

A collision is not the same thing as a symlink alias. It means two distinct real
paths share a skill name. The report lists every occurrence and tries to explain
the result separately for each tool.

An occurrence that host marks `DISABLED` does not compete or win for that host.
It remains in the collision evidence because another tool may still enable it.

| Tool | Precedence represented by the audit | Result when unresolved |
|---|---|---|
| Claude | `enterprise > personal > project`; enterprise is not filesystem-visible to this audit. | Equal project/nested paths are reported as an undeterminable tie. |
| Gemini | `workspace > user > extension > built-in`; visible project roots are workspace and global roots user. Within a tier, `.agents` wins over `.gemini`. | No winner if a usable rule cannot determine one. |
| Codex | No precedence rule is assumed. | Both entries are reported; the user selects. |

The Claude ordering is specifically skill precedence, not Claude settings
precedence. The two are opposite in a personal-versus-project conflict. The
Gemini within-tier `.agents` preference is treated as observed project knowledge,
not vendor-documented behavior. Re-checked 2026-08-06 against
`docs/cli/using-agent-skills.md`: the vendor calls the two paths "aliases" and
states no order between them, so the label stands. The supporting evidence is now
first-party runtime output rather than community report — `gemini skills list
--all` prints which path overrides which.

## Overlap candidates: exactly what is detected

Overlap is the tool’s deliberate **heuristic**, not its claim to understand
intent. It compares skill descriptions only; it does not read their bodies for
semantic contradiction, call a model, or infer the real-world purpose of a
shared trigger.

For every pair of discovered skills it:

1. lowercases each description;
2. splits it on non-word characters;
3. discards tokens under four characters;
4. discards common routing stopwords such as `when`, `user`, `use`, `create`,
   `write`, `make`, `help`, and `content`, plus equivalent personal/timing
   boilerplate such as `Ryan says`, `before`, `after`, `start`, and `end`;
5. deduplicates the remaining terms into one set per skill; and
6. intersects those sets.

It also extracts quoted substrings and compares them two ways: exactly after
lowercasing, and for **containment** — a quoted phrase of two or more words that
is a whole-word slice of a longer quoted phrase in the other skill. The shorter
trigger covers every request the longer one names, so the pair is worth reading.
Containment is a hint about model routing, never a verdict: which skill actually
gets picked is the model's call over both full descriptions and the surrounding
context, and this tool does not verify triggering.

| Signal | Result |
|---|---|
| 0–2 shared distinctive terms and no shared quoted phrase | No overlap item. |
| 3–4 shared distinctive terms | `NOTICE`, unless ownership escalation applies. |
| 5+ shared distinctive terms | `WARNING`. |
| Any identical quoted phrase | `WARNING`, regardless of word count. |
| A quoted phrase of 2+ words wholly contained in another skill's quoted phrase | `NOTICE` (`intent_shadow`), one per phrase pair, regardless of term count. |
| Both descriptions name the other skill and explicitly decline or hand off its job | Keep the overlap visible as `NOTICE`; the routing boundary is explicit rather than unresolved. |

The report includes `shared_terms`, `shared_term_count`,
`shared_quoted_phrases`, `shadowed_phrases`, `reciprocal_boundary`, and
`suppressed` in JSON. In text it says “may overlap
— read both files,” never “these conflict.” When two copies have the same skill
name, the display labels use real paths so the pair remains actionable — and a
`suppress` entry for that pair must therefore be written with those paths,
joined by ` / `, the same separator the report prints.

### Intentional sharing versus accidental duplication

The audit cannot understand a semantic boundary on its own. It can recognize the
narrow mechanical case where both descriptions name the other skill and
explicitly decline or hand off that adjacent job; that pair stays visible as a
notice. Other intentional overlaps use the two configuration mechanisms below,
which work in opposite directions and neither guesses.

`ownership` only escalates: a 3–4-term notice becomes a warning when neither
skill is the declared owner of any job area. It never silences anything.

`overlap.suppress` is the explicit human verdict, and it is the only thing that
can mute a pair. The judgement stays with the person who read both files; the
audit's job is to make the muting visible rather than to decide it. Three
properties keep an audited mute list from becoming an unaudited one:

- A muted pair still appears in JSON with `"suppressed": true`, and the text
  report prints `N suppressed by config` under **Overlap candidates**. The
  section never simply gets shorter.
- An entry that matches nothing raises `suppress_unmatched`. A renamed skill or
  a typo cannot quietly stop suppressing.
- Suppression is scoped to what you name. A pair entry mutes one pair; a bare
  skill name mutes every pair that skill appears in, including pairs formed by
  skills added later — so prefer pair entries unless you mean the wide form.

An unmatched suppression is evaluated only on an unfiltered scan. Under
`--tool`, one or both members may simply belong to an excluded host, so absence
is not evidence that the library-wide config is stale.

Suppress a pair only when you have read both files and can state the boundary in
one sentence. Suppressing to clear a report is how the heuristic stops working.

Treat an overlap result as a review queue. Keep two skills separate only when a
user can express the boundary in one short sentence. Otherwise merge them, make
one explicit-only, or rewrite descriptions around non-overlapping triggers.

### Write for distinction, not for the threshold

Do not swap synonyms just to reduce the shared-term count. That can make the
warning disappear while leaving two agents-facing descriptions equally vague.
The heuristic is a prompt to examine routing, not a game to win.

For each skill, write a small routing contract in its description or supporting
documentation:

| Part | Question it answers |
|---|---|
| **Use when** | What outcome, evidence, or request should select this skill? |
| **Do not use when** | Which nearby job belongs to another skill instead? |
| **Hand off to** | If the request crosses that boundary, which skill owns it? |

For example, a file-search skill can say it is for locating and reading files,
not editing them, and hand editing requests to the relevant implementation
skill. These explicit boundaries improve real routing even though the audit
still detects only lexical overlap.

## Findings reference

Every finding has a stable `code`, a `severity`, a human-readable `message`, and
where available a `skill`, `path`, and source `line`. Integrations should filter
on `code`, not message wording.

The severities below are the ones a finding gets against a skill you wrote. On a
vendor-installed skill the quality codes are demoted one level to `notice`; see
*Vendor-installed skills* above for which codes and why.

### Errors

| Code | Meaning | Typical repair |
|---|---|---|
| `no_frontmatter` | `SKILL.md` has no leading `---` frontmatter block. | Add a valid frontmatter block. |
| `missing_description` | Description is absent, blank, or not readable. | Add a non-empty routing description. |
| `invalid_name` | The directory or declared name violates the portable 1–64 lowercase-hyphen form. | Rename or correct the declared name, then keep both identical. |
| `invalid_description` | Description exceeds the portable 1,024-character maximum. | Shorten it; move procedure into the body. |
| `invalid_compatibility` | Compatibility is not a non-empty string of at most 500 characters. | Replace it with a concise string or remove it. |
| `invalid_metadata` | Metadata is not a string-to-string mapping. | Use an indented mapping whose keys and values are strings. |
| `unreadable` | A required skill file cannot be read. | Repair permissions, encoding, path, or the missing repository. |
| `unparseable_field` | A description field is malformed when it prevents a usable description. | Use supported YAML syntax; quote `: ` or ` #` values. |

### Warnings

| Code | Meaning |
|---|---|
| `unparseable_field` | A non-description frontmatter or Codex policy value could not be read. |
| `thin_description` / `bloated_description` | Description is outside the 40–500 character range. |
| `missing_trigger` | Description lacks a recognized routing phrase. |
| `vague_description` | Description has no signal beyond known vague terms. |
| `oversized_body` | `SKILL.md` has more than 500 lines. |
| `broken_symlink` | A scanned link cannot be resolved. |
| `double_link` | Gemini’s two global roots resolve to one target. |
| `non_portable_path` | A skill uses a legacy `~/.gemini/antigravity/skills/` or `~/.gemini/antigravity-cli/skills/` path. |
| `mode_disagreement` | Claude and Codex disagree between POCKET and SHELF. |
| `name_collision` | Two distinct real paths share a skill name. |
| `overlap` | Two descriptions meet the heuristic overlap threshold. |
| `budget_exceeded` | Claude or Codex POCKET listing total exceeds its limit. |
| `entry_cap_exceeded` | A Claude POCKET entry's effective listing text exceeds 1,536 characters. |
| `pocket_count` | More than five skills are pocket and no intent list is configured. |
| `intended_shelf_pocket` | Global pocket reality exceeds declared intent. |
| `intended_pocket_shelf` | A declared pocket skill is not pocket. |
| `intended_missing` | The configured intent names no installed skill. |
| `dangling_reference` | A body references `skills/<name>/SKILL.md` that is not in the scanned library. |
| `suppress_unmatched` | An `overlap.suppress` entry matched no detected pair. |
| `config_error` | The TOML configuration could not be parsed, or a value in it is the wrong shape and was ignored. |

### Notices

| Code | Meaning |
|---|---|
| `unknown_field` | Frontmatter contains a readable field outside the current recognized list. |
| `late_job_noun` | First 100 description characters lack a distinctive non-vague term. |
| `overlap` | A non-blocking overlap candidate, including a reciprocal named handoff. |
| `intent_shadow` | One quoted trigger phrase is a whole-word slice of another's. Never escalates: it cannot fail `--strict` on its own. |

## CLI contract

| Flag | Behavior |
|---|---|
| `--repo PATH` | Add a repository to scan; repeat it for more repositories. Each path is treated as an audit context, not proof of host folder trust. |
| `--config PATH` | Override `~/.skill-audit.toml`. |
| `--json` | Write the complete report as JSON to stdout. It overrides `--quiet`. |
| `--format github` | Emit one GitHub workflow command per finding for inline PR annotations, instead of the text report. `--json` wins over it. Never changes the exit code. |
| `--markdown PATH` | Also write the full text report inside a Markdown code block at this exact path. |
| `--quiet` | Suppress Inventory, Budget, and Pocket check in text output only. The output explicitly says they were suppressed. |
| `--tool NAME` | Restrict scanning to `claude`, `codex`, `gemini`, `antigravity`, or `claude-desktop`; repeatable. |
| `--strict` | Turn warnings into exit status 1. |
| `--version` | Print version and `PATHS_VERIFIED`, then exit. |

Exit statuses are stable:

| Status | Meaning |
|---:|---|
| 0 | No errors, or warnings without `--strict`. |
| 1 | At least one warning and `--strict` was requested. |
| 2 | At least one error. |
| 3 | An unexpected script failure. |

Notices never independently change the exit code. `--quiet` never changes it
either.

## Output and JSON schema

The top-level JSON object always contains:

```text
meta, skills, findings, collisions, overlaps, dangling_references, budget,
pocket_check, recommendations
```

`meta` records version, path-verification date, UTC scan timestamp, locations
scanned, config location, and whether configuration was present. Each skill
records its real path, source file, reachable locations, visible tools, per-tool
states, effective per-tool listing descriptions, host overrides, line and
character counts, description, scopes, precedence keys,
references to other skills, and occurrences. The collision and overlap structures retain the evidence needed to
review the high-level finding.

Text output always includes Summary, Errors, Warnings, Notices, Name collisions,
Overlap candidates, Recommended actions, and a path-stability note. Empty
sections say `none found`; a section never disappears silently, and a config-muted
overlap is counted as `N suppressed by config` rather than dropped. Normal output
also includes Inventory, Budget, and Pocket check. Quiet mode replaces those
three with an explicit suppression message.

Recommendations group identical issue messages while preserving the affected
skill names. A recurring error across several skills should therefore be one
action item with a count, not a pile of indistinguishable lines.

## What the audit intentionally does not do

1. **It does not detect semantic or behavioral conflicts.** Opposite
   instructions with no shared vocabulary are invisible to the overlap check.
2. **It does not generally distinguish intentional from accidental shared
   triggers.** A narrow reciprocal named handoff stays visible as a notice;
   every other shared phrase remains a review signal, not an intent model.
3. **It does not modify, merge, relink, or repair skills.** Repairs remain a
   human decision.
4. **It does not prove a trigger fires.** That is a separate tool in this
   repository: `route_check.py` hands a real model the pocket listing and checks
   which skill comes back. It is deliberately not part of the auditor, which
   stays offline, instant, and dependency-free.
5. **It does not guess Antigravity invocation mode or malformed host state.**
   Gemini's valid persistent on/off settings are modeled; UNKNOWN remains the
   correct result when no readable signal exists.
6. **It does not discover vendor-only or enterprise skills outside the scanned
   filesystem locations.** Precedence notes acknowledge this limitation.

## Verification and maintenance

The repository’s self-check is intentionally framework-free and uses temporary
skill trees rather than a real agent installation:

```sh
python3 test_skill_audit.py

# In environments where Python cannot create bytecode in the workspace:
PYTHONPYCACHEPREFIX=/tmp/skill-audit-pycache python3 -m py_compile skill_audit.py
```

The tests cover parser forms, wrapped descriptions, trigger recognition,
Codex’s sibling policy/interface mapping, overlap thresholds, per-tool budgets,
precedence, nested discovery, broken-link handling, project-scope pocket rules,
quiet output, JSON serializability, and empty-machine behavior.

For a release-quality change, verify three layers separately:

1. Run the self-check and compile check.
2. Run the CLI against a representative local library, including `--strict` and
   `--json` when their output contract changes.
3. If behavior depends on vendor discovery or invocation, use that vendor’s
   own inventory and a fresh-session trigger evaluation. Documentation and a
   filesystem scan are not proof that the agent loaded the skill.

## Current library map

This section is a human routing map for the library snapshot reviewed on
2026-08-06. It complements the audit: the audit detects files and metadata;
this map explains the intended division of labor. Update this table and
`skill-wiki.md` when a skill is added, removed, renamed, or deliberately moved
between POCKET and SHELF.

### Pocket skills

Pocket skills are eligible for automatic consideration in Claude Code and
Codex. Their description budget is deliberately limited, so each should have a
clear broad-use case rather than merely a convenient workflow.

| Skill | Intended job | Boundary |
|---|---|---|
| `gitnexus-cli` | Operate the GitNexus CLI: analyze, index, inspect, clean, or document a graph. | Use `gitnexus-guide` for GitNexus concepts and `gitnexus-exploring` to understand code through the graph. |
| `gitnexus-debugging` | Trace a bug, error, or failing behavior with GitNexus. | It is diagnosis-oriented; use impact analysis before a planned change. |
| `gitnexus-exploring` | Understand architecture, execution flow, or unfamiliar code. | It explains what exists; it does not judge change risk or perform a restructure. |
| `gitnexus-guide` | Explain how to use GitNexus itself. | It is product/tool guidance, not repository analysis. |
| `gitnexus-impact-analysis` | Identify dependencies and risk before changing code. | It assesses consequences; use refactoring for the actual restructure. |
| `gitnexus-refactoring` | Safely rename, extract, move, split, or otherwise restructure code. | It is change execution, not initial discovery. |
| `idea-pressure-tester` | Score or pressure-test an uncommitted idea across its decision dimensions. | It makes the go/no-go critique; accepted-project structure belongs to `new-project-kickstart`. |
| `new-project-kickstart` | Establish the foundation of an accepted creative project. | It structures a committed concept; unresolved go/no-go critique belongs to `idea-pressure-tester`. |
| `past-chat-archaeologist` | Retrieve a prior decision, artifact, or conversation result. | It looks backward; it does not create a new session record. |
| `session-handoff` | Create a compact handoff at the end of a session. | It preserves the current work; use archaeology to find older work. |
| `startday` | Produce the morning brief and orient the current day. | It is daily orientation, not generic long-horizon planning. |

### Shelf skills

Shelf skills are deliberately explicit-only in Claude Code and Codex. Name the
skill or explicitly request its specialized job when you want the workflow.

| Skill | Intended job | Boundary |
|---|---|---|
| `abcde` | Guide clarification with short A/B/C/D/E choices. | It elicits decisions; `grill-me` aggressively stress-tests a plan. |
| `audio-drama-formatter` | Format an ElevenLabs-ready audio drama or fiction-podcast script. | It is delivery formatting, not general creative development. |
| `bandwidth-snapshot` | Build a daily planning snapshot or planned-versus-actual review. | It manages capacity, not the morning agenda itself. |
| `brand-voice` | Create Human-AI Integration public content, posts, hooks, and bio copy. | It is brand-specific public copy, not generic editing or a comic script. |
| `byteworks-comic-script` | Write a four-panel ByteWorks/Botsly comic script. | It is a constrained comic format, not all brand writing. |
| `confirm-suspicions` | Run a real-output QA gate and prepare rollback. | It validates a proposed/implemented outcome; `spell-pierce` targets adversarial edge cases before shipping. |
| `edit-article` | Restructure, clarify, and tighten an article. | It edits prose rather than enforcing the Human-AI Integration brand voice. |
| `eternal-witness` | Turn a reusable completed-session procedure into a skill. | It creates a durable workflow artifact; `session-handoff` merely preserves current context. |
| `expedition-map` | Map an unfamiliar codebase before changing it. | It is a structured codebase survey; GitNexus exploration is the graph-powered alternative. |
| `grill-me` | Stress-test a plan or design through relentless questions. | It is adversarial interrogation, not lightweight option-based clarification. |
| `horror-voice` | Apply shared craft rules when writing horror fiction. | It is genre-specific fiction craft, not a general creative-project setup. |
| `parody-brand` | Create a parody-brand package: concept, voice, products, and script. | It creates a new fictional brand, not the established Human-AI Integration voice. |
| `preordain` | Write a narrative pull-request description from the current diff. | It summarizes a change for review; it does not perform the code review. |
| `spell-pierce` | Conduct adversarial edge-case testing before shipping. | It seeks failure cases, whereas `confirm-suspicions` is a broader output/rollback gate. |
| `teferis-protection` | Apply guardrails before destructive or stateful CLI actions. | It is operational safety, not a general testing or code-exploration workflow. |

### PKOS suite skill

| Skill | Intended job | Current integration note |
|---|---|---|
| `pkos-ingest` | Preserve and normalize local files, folders, notes, generic ZIPs, and ChatGPT export ZIPs into PKOS. | Canonical location is `~/.skills/pkos-ingest`, linked through the shared path. Claude Code and Gemini activation still needs a fresh mode/listing verification. |

Gemini reports POCKET or DISABLED from its effective persistent settings.
Antigravity remains UNKNOWN: that says the audit lacks a readable state signal,
not that a skill cannot be used.

## Related documents

- [README.md](../README.md) — compact install, command, and output reference.
- [library-model.md](library-model.md) — the orientation model: canonical copy,
  discovery, invocation mode.
- [HAPPYPATH.md](HAPPYPATH.md) — a practical sequence for repairing a library.
- [dos-and-donts.md](dos-and-donts.md) — finding-by-finding remediation guide.
- [exemplars/skill-example.md](exemplars/skill-example.md) — one verified-clean
  skill, annotated line by line.
- Authoring assistants, paste-ready:
  [Claude Project](claude-project-skill-instructions.md),
  [Custom GPT](custom-openai-gpt-skill-instructions.md),
  [Gemini Gem](custom-gemini-skill-instructions.md).
- [OVERLAP-REVIEW.md](OVERLAP-REVIEW.md) — a dated review queue for the current
  live library; it is not a general rulebook.
- [skill-wiki.md](skill-wiki.md) — dated inventory and routing notes for the
  current installed skill library.
- `route_check.py` — the routing harness: the model-in-the-loop counterpart to
  this static auditor. See the README's Routing harness section.
- [brief.md](../brief.md) — original implementation specification.

## Decision record: why the tool is conservative

The auditor favors transparent false positives over invisible false negatives.
It labels word similarity as a candidate, leaves undocumented states UNKNOWN,
and refuses YAML constructs it cannot parse with confidence. Those choices can
produce a review task, but they avoid the more damaging outcome: reporting a
library clean after silently misunderstanding its metadata, links, or tool
state.

When this manual and the code disagree, the current implementation in
`skill_audit.py` is authoritative. Update both in the same change whenever the
public behavior changes.
