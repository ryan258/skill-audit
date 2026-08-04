# Making sure each AI actually uses your skills

Need the conceptual map before the per-tool details? Read
[The skill-library model](docs/library-model.md). This guide focuses on the
discovery, listing, and invocation checks after you have chosen a canonical
personal copy.

A skill file existing on disk means nothing. Four things have to be true, in order, before an agent will use it:

1. **Installed** — the tool is on the machine and runs
2. **Discovered** — the tool looks in a directory your skill is in
3. **Listed** — the tool parsed the frontmatter and put the description in context
4. **Invocable** — the description is specific enough that the agent reaches for it

`skill_audit.py` verifies 2 and 3. Step 1 is a shell check. Step 4 can only be confirmed by running the agent — no static tool can tell you a skill will fire.

Most "my skill isn't working" problems are step 2, and they're invisible unless you look.

---

## The one-source-folder model

Keep every skill in one directory. Point each tool at it. Never copy.

```
~/.skills/                    ← the only place a SKILL.md actually lives
├── brand-voice/
│   └── SKILL.md
└── session-handoff/
    └── SKILL.md
```

Then each tool's skills directory holds symlinks (or per-tool links) back to that source. Edit once, all four of those tools see the change. **Claude Desktop does not** — it reads a separate library synced from your account, so a `~/.skills/` edit never reaches it. Change that copy in the app: Settings → Skills → the skill → Replace.

`skill_audit.py` resolves every symlink and deduplicates by real path, so a skill reachable from four tools reports as **one** entry with four reachable-from paths — not four skills.

The trap this avoids: copying skills into four directories, editing one, and spending a week confused about why the agent uses a stale version.

---

## Claude Code

**Path:** `~/.claude/skills/`

**Wire up:**
```sh
ln -s ~/.skills/brand-voice ~/.claude/skills/brand-voice
```

**Verify:** run `/context` in a session, or ask the agent directly: *"list the skills you can see and say which are auto-invocable."* The description of every pocket skill sits in context every session, so the agent can read them back to you.

**Shelf a skill:** add to the frontmatter:
```yaml
disable-model-invocation: true
```
It stays available via `/skill-name` but the agent won't reach for it on its own.

---

## Gemini CLI

**Path:** `~/.agents/skills/` or `~/.gemini/skills/` — but prefer the built-in command over hand-linking.

**Wire up:**
```sh
gemini skills link ~/.skills/brand-voice
```

`gemini skills link` keeps the source live — edits show up immediately, same as a symlink, but Gemini records it properly.

**Verify:**
```sh
gemini skills list --all
```
This is the most useful verification command of any of the CLI tools. It prints every discovered skill with `[Enabled]` / `[Disabled]`, the description, and the resolved file location. If your skill isn't in that output, Gemini cannot see it — nothing else matters until that's fixed.

**Shelf a skill:** there is no shelf. `gemini skills disable <name>` exists but it's a blunter instrument — it removes the skill from consideration entirely rather than making it explicit-invocation-only. `skill_audit.py` reports Gemini state as `UNKNOWN` for this reason, and excludes those skills from budget math.

**Watch for the double link.** If both `~/.agents/skills/` and `~/.gemini/skills/` resolve to the same target, Gemini reads both as user scope and the same skill lands in the same tier twice. The audit flags this as `double_link`.

**Precedence, highest first.** Gemini resolves duplicates across four scanned tiers:

| Priority | Tier | Path |
|---|---|---|
| 1† | Workspace | `<repo>/.agents/skills/` |
| 2 | Workspace | `<repo>/.gemini/skills/` |
| 3† | User | `~/.agents/skills/` |
| 4 | User | `~/.gemini/skills/` |
| 5 | Extension | bundled extension paths |
| 6 | Built-in | CLI built-ins |

*† The four main tiers (Workspace > User > Extension > Built-in) are official Gemini CLI precedence rules; the within-tier `.agents/skills/` > `.gemini/skills/` preference (rows 1 vs 2, 3 vs 4) is observed via community testing rather than official documentation.*

Extension and built-in skills don't live in a scanned path, so the audit resolves the top four and names the winner per tool. Pick one home for a skill anyway — relying on precedence to break a tie you created is how you end up editing the copy that never loads.

**Folder trust:** `gemini skills list` will print `Skipping project agents due to untrusted folder` when run in an untrusted directory. Project-scope skills silently don't load until you trust the folder — this looks exactly like a broken skill.

---

## Codex

**Path:** `~/.agents/skills/` (moved from `~/.codex/skills` — if you set this up more than a few months ago, your skills are in the old location. The audit scans both, so they'll show up either way.)

**Wire up:**
```sh
mkdir -p ~/.agents/skills
ln -s ~/.skills/brand-voice ~/.agents/skills/brand-voice
```

**Verify:** ask the agent to list what it can see. Codex has no `skills list` equivalent.

**Shelf a skill:** per-skill file at `<skill-dir>/agents/openai.yaml`:
```yaml
policy:
  allow_implicit_invocation: false
```
There is no repo-level or home-level version of this file. Absent means pocket.

`openai.yaml` may carry an `interface:` block alongside `policy:`. The audit reads both one-level mappings; only `policy.allow_implicit_invocation` affects shelf detection.

**Name collisions don't resolve here.** Claude and Gemini both have documented precedence rules. Codex doesn't — both entries can appear in the picker and the user chooses. Duplicate names are a real problem for Codex in a way they aren't elsewhere.

---

## Antigravity

**Path:** `~/.gemini/config/skills/`

This is the only global path confirmed to work across all three Antigravity flavors. Two others exist and partly work:

- `~/.gemini/antigravity/skills/`
- `~/.gemini/antigravity-cli/skills/`

`skill_audit.py` scans both and flags anything found there as **non-portable**. Antigravity has three official docs that disagree with each other; the evidence for `~/.gemini/config/skills/` is community testing, not documentation. Re-check it.

**Shelf a skill:** no documented mechanism. Reports as `UNKNOWN`.

---

## Current state of this machine

Checked August 4, 2026:

| Tool | Installed | Sees your skills? |
|---|---|---|
| Claude Code | yes | **yes** — 28 skills |
| Gemini CLI | yes | **yes** — 28 skills (30 rows incl. built-ins) |
| Codex | yes | **yes** — 58 skills (also reads `~/.codex/skills`) |
| Antigravity | path present | 28 skills discoverable; mode UNKNOWN |
| Claude Desktop | yes | **yes** — from its own account-synced library (count omitted on purpose, see below) |

`~/.skills/` holds 29 skills, and all four cupboard paths — `~/.claude/skills/`,
`~/.agents/skills/`, `~/.gemini/skills/`, `~/.gemini/config/skills/` — now exist
and resolve to it. The wiring below is what got them there; it is kept as the
recipe, not as a description of a broken machine.

Claude Desktop's skills are a **separate library** and are not served by any of
that wiring. See [docs/library-model.md](docs/library-model.md). No count is
recorded here: that library syncs from your account and changes without a local
edit — it gained a skill mid-session while this page was being written. For the
current number run `python3 skill_audit.py --tool claude-desktop`, or read the
regenerated [skill wiki](docs/skill-wiki.md), which is dated for that reason.

To fix Gemini:
```sh
for d in ~/.skills/*/; do gemini skills link "$d"; done
gemini skills list --all
```

To fix Codex, reinstall it first — `codex --help` currently fails with `ENOENT` on a missing vendored binary — then create `~/.agents/skills/` and link.

---

## The verification loop

After any change, in this order:

```sh
python3 skill_audit.py              # discovered + parsed correctly?
gemini skills list --all            # Gemini's own view
```

Then open each agent and ask it to list its skills. The audit tells you what's on disk and readable. Only the agent tells you what's actually in its context.

**Then test step 4.** Start a fresh session and give it the trigger phrase from the description — not the skill name. If the agent doesn't reach for the skill, the description is the problem, not the wiring. Descriptions that fail here usually lack a concrete trigger ("Use when the user asks for X") or are so broad they compete with three other skills. The audit's `missing_trigger` and `overlap` findings point at exactly this.

---

## Budget

Every pocket skill's description sits in context every session, in every tool, forever. That's the real cost, and it's why the shelf exists.

Rough ceilings: Claude allots about 1% of the context window to the skill listing with individual entries capped near 1,536 characters; Codex uses at most 2%, or 8,000 characters when the window is unknown. `skill_audit.py` sums pocket name + description characters against both and warns when either is over.

Skills you invoke by name deliberately should be shelved. Skills the agent needs to *notice* on its own should be pocket, and there should be few of them. If you have more than five pocket skills and no config declaring that's intentional, the audit warns.

Note what the budget number excludes: Gemini and Antigravity skills report `UNKNOWN`, so they're left out of the totals. The audit prints the excluded count alongside each figure — a passing budget with 20 exclusions is not a passing budget.
