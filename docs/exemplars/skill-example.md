# Exemplar: a skill that passes `--strict`

`dos-and-donts.md` is the failure catalogue. This is the opposite: one complete
skill, written correctly, with the reasoning in the margin. Copy it and replace
the domain.

The skill below is verified — `skill_audit.py --strict` reports zero findings
against it.

---

## The file

`~/.skills/release-notes/SKILL.md`

```markdown
---
name: release-notes
description: Drafts release notes from merged PRs in this repo's house format. Use when the user cuts a release or asks what shipped since a tag.
allowed-tools: [Read, Grep, Bash]
---

# Release notes

## When this runs

The user is cutting a release, or asking what changed since some point. If they
want a changelog file rewritten wholesale, that's a different job — say so.

## Steps

1. Resolve the range. Default `git describe --tags --abbrev=0`..`HEAD`.
   If the user named a tag or date, use theirs.
2. `git log --merges --pretty='%s%n%b' <range>` — merged PRs only. Direct
   commits to main are noise in release notes.
3. Group by the conventional-commit prefix already in the subject lines:
   Added / Fixed / Changed / Removed. Drop anything prefixed `chore:` or `docs:`.
4. One line per entry, user-visible effect first, PR number last:
   `- Retries now back off exponentially instead of failing at 3 (#412)`
5. Print the draft. Never write to `CHANGELOG.md` — the user does that.

## Rules

- Breaking changes get their own section at the top, always, even for one entry.
- No entry for a PR whose effect a user cannot observe.
- If the range has zero merges, say so and stop. Don't pad.

## Format reference

See `format.md` in this directory for the full house style, including the
deprecation-notice wording.
```

---

## Why each part is the way it is

**`name` matches the directory.** `release-notes/` holds `name: release-notes`.
The directory is what every tool keys on; a mismatch is `name_mismatch` and the
skill routes under a name you didn't write.

**The distinctive noun is first.** `Drafts release notes` — noun in the first 20
characters, not the first 120. The router reads descriptions, and it reads the
front of them hardest. Opening `Helps the user create content for…` would have
buried the only word that distinguishes this skill from every other one.

**The trigger is in a recognized form.** `Use when the user cuts a release…`
matches the audit's `Use when …` pattern, which is also the pattern a router
recognizes. It names two concrete situations, not a category.

**It's 147 characters.** Over 40 (`thin_description`), well under 500
(`bloated_description`), and `name` + `description` is nowhere near the 1536-char
listing cap. This description is paid for on every single session — that's the
budget it has to justify.

**`allowed-tools` is narrow.** Three tools, all of which the steps actually use.
Not a check the audit makes, but an unbounded tool list is a skill you can't
reason about.

**No `disable-model-invocation`.** This one is POCKET on purpose: the agent
should reach for it when someone says "what shipped?" without being told the
skill exists. That's the whole test — if you'd have invoked it by name anyway,
shelve it instead.

**The body says when *not* to run.** "If they want a changelog file rewritten
wholesale, that's a different job." A skill that never declines will fire on
adjacent work and produce confident garbage.

**The steps are executable.** Real commands, a stated default, and a stated
override. Compare "gather the relevant commits" — which reads fine and gives an
agent nothing to do.

**Step 5 names the thing it must not do.** Prohibitions belong next to the step
they constrain, not in a section at the bottom that gets skimmed.

**Detail lives in a sibling file.** `format.md` holds the house style. The body
stays short enough to read in one pass, and nowhere near `oversized_body`'s
500-line ceiling.

---

## The shelf variant

Same skill, invoked only by name. Two lines change:

```diff
 ---
 name: release-notes
 description: Drafts release notes from merged PRs in this repo's house format. Use when the user cuts a release or asks what shipped since a tag.
 allowed-tools: [Read, Grep, Bash]
+disable-model-invocation: true
 ---
```

And, if Codex can see it, `agents/openai.yaml` in the same directory:

```yaml
policy:
  allow_implicit_invocation: false
```

Set one and not the other and you get `mode_disagreement` — the skill is silent
in one tool and auto-firing in the other, which is the confusing half of both
worlds. The description still has to be good: it's what the user reads in the
picker.

---

## Installing the one copy

One real directory, symlinked into each tool's path:

```sh
mkdir -p ~/.skills
# ... write ~/.skills/release-notes/SKILL.md ...
ln -s ~/.skills/release-notes ~/.claude/skills/release-notes
ln -s ~/.skills/release-notes ~/.agents/skills/release-notes
```

The audit resolves symlinks and dedupes by real target, so this reports as **one**
skill reachable from two paths. Copying the directory instead reports as a
`name_collision` between two files that will drift apart by the second edit.

---

## Check it

```sh
python3 skill_audit.py --strict
```

Clean means discoverable, parseable, and within budget. It does not mean the
agent will pick this skill on a given prompt — nothing here can tell you that.
That's an eval. See the closing section of `dos-and-donts.md`.

---

## Related

- `dos-and-donts.md` — every rule above, stated as the finding you get when you break it
- `HAPPYPATH.md` — the once-through sequence for a whole library
- `../skill-setup.md` — per-tool wiring and how to confirm each tool sees it
