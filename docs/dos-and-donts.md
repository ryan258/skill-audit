# Do's and don'ts

Every rule here maps to a finding code `skill_audit.py` actually emits. If a rule
isn't worth a code, it isn't worth a rule.

`../skill-setup.md` covers per-tool wiring and `HAPPYPATH.md` the sequence to
follow once. This file is the failure catalogue: what people get wrong, and what
the audit says when they do.

---

## Descriptions

The description is the whole routing decision. The agent picks a skill by reading
descriptions, not bodies — a perfect 400-line body behind a vague description
never runs.

**Do state the boundary, not just the job.** A good description says what selects
the skill and, where a nearby skill exists, what does not. Do not rewrite with
synonyms merely to lower an overlap count; that hides a review signal without
making routing clearer. See [the routing-contract guidance](living-manual.md#write-for-distinction-not-for-the-threshold).

**Do put the distinctive noun in the first 100 characters.**

```yaml
description: Brand voice rules for public writing. Use when the user drafts a post.
```

**Don't open with filler verbs.** `create`, `generate`, `write`, `make`, `help`,
and `content` are stopwords to the audit, because they're stopwords to a router
too — every skill claims them.

```yaml
# → notice: late_job_noun
description: Create content for the user that you write and make
```

That line has no distinctive term at all in its first 100 characters. It reads
like a job description and routes like noise.

**Don't write a description that is only filler.** `helps`, `general`, `various`,
`anything`, `assists`, `things` — if these are all that's left after stopwords,
you get `vague_description`. This check is deliberately narrow: it fires only
when there is nothing else, so a hit means the description is genuinely empty of
signal, not merely wordy.

**Do state when it fires, in words the checker recognizes.** Accepted forms:

| Phrase | Example |
|---|---|
| `Use when …` | `Use when the user asks for a tone pass.` |
| `Use before …` / `Use after …` | `Use before publishing a story.` |
| `Use at the start/end of …` | `Use at the end of a completed session.` |
| `When the user …` | `When the user pastes a stack trace.` |
| `for … requests` | `for incident postmortem requests` |

Anything else is `missing_trigger`. Note that `use as` is deliberately *not*
accepted — it matches ordinary prose ("a palette to use as inspiration") and
would defeat the check.

**Do keep it between 40 and 500 characters.** Under 40 is `thin_description` and
almost certainly can't route. Over 500 is `bloated_description` — that's body
material sitting in every session's context.

**Don't let `name` + `description` exceed 1536 characters.** That's Claude's
per-entry listing cap (`entry_cap_exceeded`). Past it, the entry is a liability
whatever it says.

---

## One copy on disk

**Do keep one real folder and link to it.** One source directory, symlinked into
each tool's path. The audit resolves symlinks and dedupes by real target, so one
folder reachable from four cupboards reports as **one** skill with a
reachable-from list — which is what you want to read.

**Don't copy a skill into each tool's directory.** Copies drift. Two copies of
one name is `name_collision`, and the report then has to tell you which one wins
under each tool's precedence — including the fact that Claude's skill precedence
(personal beats project) is the **opposite** of Claude's settings precedence, and
that Codex doesn't resolve collisions at all; it asks you to pick.

**Don't point two of a tool's paths at the same target.** If `~/.gemini/skills`
and `~/.agents/skills` resolve to the same place you get `double_link` — harmless
but a sign the wiring was done twice.

**Do clean up dangling links.** Each one is its own `broken_symlink` finding,
including links nested below the scan root, and including two separate links that
happen to point at the same missing target. Two dead links are two cleanups.

**Don't use `~/.gemini/antigravity/skills/` or `~/.gemini/antigravity-cli/skills/`.**
Both are scanned and flagged `non_portable_path`. Only `~/.gemini/config/skills/`
is confirmed across all three Antigravity flavors — and that evidence is community
testing, not vendor documentation.

---

## Pocket vs shelf

POCKET means the agent invokes it on its own, so its description sits in context
**every session**. SHELF means explicit invocation only.

**Do shelve anything you'd invoke by name anyway.** A skill you always call
deliberately costs you context for nothing as POCKET.

**Don't leave everything pocket by default.** Both budgets are small, and they
fill faster than people expect:

```
Claude: 2259/2000 chars across 12 pocket skills (over)
Codex:  10907/4000 chars across 41 pocket skills (over)
```

That's a real 57-skill library. Claude's budget is 1% of the context window,
Codex's is 2% capped at 8000.

**Do write down which skills are meant to be pocket**, in `~/.skill-audit.toml`:

```toml
[pocket]
skills = ["startday", "session-handoff", "brand-voice"]
```

Without it, the audit can only warn once you pass five pocket skills
(`pocket_count`). With it, it names the drift in both directions:
`intended_shelf_pocket`, `intended_pocket_shelf`, and `intended_missing` for a
config entry with no skill on disk — a stale config or a typo, not a mistaken flag.

**Don't expect the config to govern a repo's own skills.** Project-scope skills
are counted and listed separately, never measured against a global pocket list.

**Don't set the two tools' flags to disagree.** `disable-model-invocation: true`
for Claude and `policy.allow_implicit_invocation: false` in `agents/openai.yaml`
for Codex are the same intent; setting one and not the other is
`mode_disagreement`. Gemini and Antigravity have no documented flag, so they
report `UNKNOWN` — expected, not a failure.

---

## Frontmatter

The parser accepts an intentionally small YAML subset and **flags** anything
outside it rather than guessing. A guess here silently corrupts every downstream
check.

**Do quote a description containing `: ` or ` #`.** These genuinely terminate a
YAML plain scalar:

```yaml
description: Does a thing: then another        # → error: unparseable_field
description: "Does a thing: then another"      # fine
description: Refactors C# code                 # fine — a bare # is legal
```

**Don't use anchors, aliases, tags, or inline flow mappings** (`&ref`, `*ref`,
`!tag`, `{a: 1}`). All rejected, all `unparseable_field`. Supported forms are
plain scalars, quoted scalars, flow lists (`[Read, Grep]`), block lists, and
block scalars (`|`, `>`).

**Do match `name` to the directory name.** Mismatch is `name_mismatch`; the
directory is what the tools key on.

**Don't invent frontmatter fields.** Recognized: `name`, `description`,
`allowed-tools`, `disable-model-invocation`, `paths`, `when_to_use`, `license`,
`metadata`, `compatibility`, `argument-hint`. Anything else is `unknown_field` —
a notice, not an error, since vendors add fields.

**Do keep `SKILL.md` under 500 lines.** Past that is `oversized_body`; move
detail into sibling reference files the skill points at.

---

## Running it

**Do run it before you debug a skill that "isn't working."** Most of those are
discovery problems — the tool never looked in that directory — and they're
invisible until something enumerates the paths for you.

**Do use `--strict` in CI and plain mode locally.** Warnings exit 0 by default on
purpose: a thin description shouldn't break a pipeline you didn't intend it to.

**Don't filter on message text.** Filter on `code` — the messages are written for
humans and will be reworded. The full list is `FINDING_CODES` at the top of
`skill_audit.py` (25 codes).

**Don't read overlap findings as conflicts.** Overlap is word similarity between
descriptions — a hint to go read both files. Two skills can give flatly opposite
instructions in prose that shares no vocabulary, and this tool will never catch
that. See `OVERLAP-REVIEW.md`.

**Don't trust the paths indefinitely.** `PATHS_VERIFIED` prints on every run.
Codex has already moved once (`~/.codex/skills` → `~/.agents/skills`; both are
still scanned, because the old one still holds installs). Re-verify quarterly and
update `GLOBAL_PATHS`.

---

## The one it can't check

A skill can pass every check here and still never fire. Whether an agent actually
reaches for it on a given prompt requires running the agent — that's an eval, not
an audit. A clean report means the skill is **discoverable and listed**, which is
necessary and not sufficient.
