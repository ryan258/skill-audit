# The happy path

The shortest route from a pile of `SKILL.md` files to a library that four agents use correctly and you can keep clean.

Read this once, top to bottom. `../skill-setup.md` is the per-tool reference you'll dip back into; `../README.md` is the flag reference. This is the sequence.

---

## What "good" looks like

```
~/.skills/                     one source folder, the only place a SKILL.md lives
├── brand-voice/SKILL.md       every skill a directory with a description that routes
└── session-handoff/SKILL.md

~/.claude/skills/*  →  ~/.skills/*      each tool links back to the source
~/.agents/skills/*  →  ~/.skills/*
~/.gemini/…         →  (gemini skills link)

~/.skill-audit.toml            declares which skills are meant to be pocket

$ python3 skill_audit.py       exits 0, budget passes, pocket matches intent
```

Five properties, in priority order. Each step below establishes one:

1. One copy of every skill
2. Descriptions specific enough to route
3. Few pocket skills, deliberately chosen
4. Every tool actually pointed at the source
5. A config that records intent, so drift is detectable

---

## 1. Collapse to one source folder

Pick `~/.skills/`. Move every real skill directory there. Nothing else holds a `SKILL.md`.

```sh
mkdir -p ~/.skills
mv ~/.claude/skills/some-real-dir ~/.skills/
```

Then confirm nothing is duplicated:

```sh
python3 skill_audit.py
```

The audit deduplicates by resolved real path, so a skill reachable from four tools shows up **once** with four reachable-from entries. If the same name appears as two separate entries with different real paths, you have two copies — that's the `name_collision` section, and it tells you which one each tool would actually load.

Fix collisions now. Everything downstream assumes one copy.

---

## 2. Write descriptions that route

The description is the whole routing mechanism. The agent sees the name and description, nothing else, and decides from that.

A description that routes:

```yaml
description: Generate on-brand content for X and LinkedIn using a locked
  constraint-driven voice. Use when the user asks for posts, hooks, essays,
  or bio copy. Triggers include "write a post", "draft a hook", "X thread".
```

Three parts: **what it does**, **routing guidance**, **literal trigger phrases**. The audit accepts `use when`, `use before`, `use after`, `use at the start/end of`, `trigger`, `when the user`, or `for … requests` as routing guidance. (`use as` is not accepted — it matches ordinary prose like "a palette to use as inspiration".) It checks the rest indirectly — `thin_description` (under 40 chars), `missing_trigger`, `vague_description` (nothing but broad words), and `late_job_noun` (no distinctive term in the first 100 characters).

Two syntax rules that bite:

- A plain YAML scalar **cannot contain `": "` or `" #"`.** A description like `…the full build sequence: premise, bible, cast` is a genuine YAML error, not an audit quirk. Wrap the value in quotes.
- Wrapping a long description across several indented lines **is** fine — YAML folds the continuation lines with single spaces, and the audit reads the whole thing.
- Keep `SKILL.md` under 500 lines. Over that, move detail into supporting files next to it and reference them. The body loads when the skill fires; the description loads always.

Aim for a clean Errors section before moving on. Warnings can wait.

---

## 3. Decide pocket vs shelf, and be stingy

**Pocket** = the agent invokes it on its own; its description sits in context every session forever. **Shelf** = explicit invocation only.

The default is pocket, which is why libraries drift expensive. Ask one question per skill:

> Do I need the agent to *notice* this without being told?

Usually no. A skill you invoke by name — `/brand-voice`, `/session-handoff` — should be shelved. It stays fully available; it just stops charging you context rent.

Shelf a skill in Claude:

```yaml
disable-model-invocation: true
```

Shelf it in Codex — per skill, at `<skill-dir>/agents/openai.yaml`:

```yaml
policy:
  allow_implicit_invocation: false
```

Gemini and Antigravity have no shelf mechanism. The audit reports them `UNKNOWN`, which is the honest answer, not a gap to work around.

**Target five or fewer pocket skills.** The audit warns above five when no config declares otherwise. Five auto-invocable skills the agent picks between reliably beats twenty it picks between badly.

Set both flags on the same skill when you mean it. The audit raises `mode_disagreement` when Claude and Codex disagree, because that's almost always a half-finished edit rather than a decision.

---

## 4. Wire each tool to the source

Per-tool commands and paths are in `../skill-setup.md`. The short version:

```sh
# Claude Code
ln -s ~/.skills/brand-voice ~/.claude/skills/brand-voice

# Codex
mkdir -p ~/.agents/skills && ln -s ~/.skills/brand-voice ~/.agents/skills/brand-voice

# Gemini CLI — use its own command, not a manual symlink
gemini skills link ~/.skills/brand-voice
```

Then confirm each tool's own view, because the audit only proves the files are readable — not that a tool loaded them:

```sh
gemini skills list --all
```

For Claude and Codex, open a session and ask the agent to list the skills it can see. If a skill isn't in that list, nothing else in this document matters yet.

One trap worth naming: don't link **both** `~/.agents/skills` and `~/.gemini/skills` to the same target. Gemini reads both as user scope and the skill lands in the same tier twice. The audit flags that as `double_link`.

---

## 5. Record intent in a config

Without a config the audit can only count pocket skills. With one it can tell you when reality drifted from what you decided.

`~/.skill-audit.toml`:

```toml
[pocket]
skills = ["startday", "session-handoff", "brand-voice"]

[ownership]
# Which skill owns a job area. Overlap between two skills where neither is
# a declared owner gets escalated from NOTICE to WARNING.
"morning brief" = "startday"
"public content" = "brand-voice"

[budget]
context_window = 200000
```

Now the pocket check reports lists instead of a bare count: correct, intended-shelf-but-actually-pocket (a missing flag), intended-pocket-but-actually-shelf (a flag added by mistake), in-config-but-not-installed (a typo or a stale entry), and project-scope pocket skills.

That last list is informational. A repo's own skills aren't governed by your global pocket list, so they're counted but never reported as drift against it.

---

## 6. Get to exit 0

```sh
python3 skill_audit.py
echo $?
```

A clean run:

```text
Summary
-------
12 unique skills; 4 pocket in at least one tool; 24 discovered entries; 7 locations scanned
config: /Users/you/.skill-audit.toml

Errors
------
none found

Budget
------
Claude: 1180/2000 chars across 4 pocket skills (pass)
Codex:  1180/4000 chars across 4 pocket skills (pass)
0 skills excluded: only Gemini/Antigravity can see them, and their mode is UNKNOWN

Pocket check
------------
rule: a skill counts as pocket if it is POCKET in at least one tool that can see it
pocket count: 4
correct: brand-voice, session-handoff, startday
```

Read the exit code, not the vibe:

- **`0`** — clean, or warnings only. Warnings are advisory by design; a thin description or a possible overlap is something to read, not something that should break a pipeline.
- **`2`** — errors. A skill is unreadable or has no usable description, which means it is not routable. Fix these.

Once you're at 0, lock it in with `--strict` so warnings start failing too:

```sh
python3 skill_audit.py --strict
```

That's the real end state. Getting to `--strict` clean and staying there is the point of the whole exercise.

---

## 7. Prove it fires

The audit is static. It cannot tell you a skill will actually trigger — that requires running the agent, and it's an eval, not an audit.

So: open a fresh session and use a **trigger phrase from the description**, never the skill name.

> "draft a hook for a post about constraint-driven design"

If the agent reaches for `brand-voice`, the routing works. If it doesn't, the description is the problem, not the wiring — go back to step 2. If the *wrong* skill fires, two descriptions are competing; that's what the overlap section was hinting at.

Do this for each pocket skill once. Shelf skills don't need it — you invoke those by name.

---

## The maintenance loop

**After any change to a skill:**

```sh
python3 skill_audit.py --strict
```

**Before adding a new pocket skill,** check the budget line first. Something usually has to move to the shelf to make room. The listing budget is roughly 1% of the context window for Claude, 2% (or 8,000 characters) for Codex.

**Quarterly,** re-verify the paths. The `PATHS_VERIFIED` date prints on every run:

```sh
python3 skill_audit.py --version
```

Codex has already moved from `~/.codex/skills` to `~/.agents/skills`, Antigravity has three official docs that contradict each other, and the evidence for `~/.gemini/config/skills/` working across all three of its flavors is community testing rather than documentation. When a date is more than a quarter stale, check the vendor docs and update `GLOBAL_PATHS` at the top of `skill_audit.py`.

**When something breaks mysteriously,** work the four steps in order — installed, discovered, listed, invocable. Most failures are step 2, and they're silent.
