# Skill wiki

Snapshot: 2026-08-03. This is a live-library reference, not a claim that every
agent will select a skill for every matching prompt.

## What is installed where

| Surface | Location | Current state |
|---|---|---|
| [Claude Code](https://docs.anthropic.com/en/docs/agents-and-tools/claude-code/overview) | `~/.claude/skills/` | 27 filesystem entries, including the linked `pkos-ingest` ([PKOS](https://github.com/ryan258/PKos)); 26 shared skills were verified live before it was added. |
| [Codex](https://openai.com) | `~/.codex/skills/` plus `~/.agents/skills/` | Bundled/runtime skills remain in the Codex directory; personal shared skills resolve through the shared path. |
| [Gemini CLI](https://gemini.google.com) | `~/.agents/skills/` → `~/.claude/skills/` | The shared `pkos-ingest` link resolves here; re-run `gemini skills list --all` after a Gemini restart to refresh its inventory. |
| [Antigravity](https://antigravity.google) / Antigravity IDE | `~/.gemini/config/skills/` → `~/.agents/skills/` | The shared `pkos-ingest` link resolves on the configured path. Its activation mode is undocumented, so it remains `UNKNOWN`. |
| Claude Desktop Chat/Cowork plugins | Account-level Claude plugin directory | No Claude plugins installed as of this snapshot; this is separate from the local skill library. |

The personal source of truth is `~/.skills/`. Its entries are linked into
`~/.claude/skills/`, then exposed to the other coding agents through the shared
directory aliases. Bundled/runtime skills remain at their tool-managed paths;
they are not copied into the personal library.

## Canonical-copy model

There should be **one physical `SKILL.md` per skill**, with the other agents
reaching it by links. The common routing chain is:

```text
Claude Code:          ~/.claude/skills/<skill>
                              ↑
Gemini CLI:            ~/.gemini/config/skills -> ~/.agents/skills -> ~/.claude/skills
Antigravity products:  ~/.gemini/config/skills -> ~/.agents/skills -> ~/.claude/skills
```

`pkos-ingest` now follows the same rule as every other personal shared skill:

```text
~/.claude/skills/pkos-ingest -> ~/.skills/pkos-ingest
```

One physical `SKILL.md` serves Claude Code, Codex, Gemini, and Antigravity
through the shared path chain. This canonical-copy rule applies to personal
skills; bundled/runtime skills remain tool-managed.

Claude Desktop is intentionally outside this chain. Its **Customize → Plugins**
inventory does not auto-load `~/.claude/skills/`. To use a shared skill in
Claude Desktop, package a Desktop plugin or local extension that exposes the
canonical skill; do not duplicate the `SKILL.md`.

## Reading the entries

- **P** — POCKET in both Claude Code and Codex: eligible for automatic use.
- **S** — SHELF in both Claude Code and Codex: invoke by name or with a very
  explicit request.
- **Gemini / Antigravity** — their automatic-invocation state is `UNKNOWN`; do
  not infer that an enabled/listed skill is automatic or shelf-only.
- Every listed personal skill is on the shared filesystem path for Claude Code,
  Codex, Gemini, and Antigravity. The **AI** column records the verified mode
  where one exists.

## Happy path

1. Start with the outcome you want, not the skill name. The matching skill's
   description is the routing contract.
2. On Claude Code or Codex, expect a **P** skill to be considered
   automatically. For an **S** skill, say its name or explicitly request its
   job (for example, “use `preordain` to write the PR summary”).
3. On Gemini, confirm the skill appears in `gemini skills list --all`. Restart
   Gemini first if you just added or linked a skill.
4. On Antigravity or Antigravity IDE, use the same request but treat activation
   as unverified until the app exposes a skill inventory or demonstrates a
   matching action.
5. After editing a description, run `python3 skill_audit.py`. A clean result
   means the metadata and paths are readable; it is not a behavioral trigger
   evaluation.

## PKOS suite skill

This operational skill is shared alongside the pocket/shelf library. Its
automatic-invocation state in Claude Code and Gemini has not been re-verified
since the link was added, so name it explicitly there for now.

| Skill | Canonical location | Use it when | AI |
|---|---|---|---|
| `pkos-ingest` | `~/.skills/pkos-ingest/` → `~/.claude/skills/pkos-ingest/` | You need to locally preserve and normalize files, folders, notes, generic ZIPs, or ChatGPT-export ZIPs into PKOS. | Shared through the same path chain as the other personal skills; Claude Code/Gemini activation still needs a fresh live verification; Claude Desktop requires a plugin wrapper. |

## Pocket skills

These are the deliberate always-considered skills for Claude Code and Codex.
They consume 1,936 of the 2,000-character Claude listing budget.

| Skill | Location | Use it when | AI |
|---|---|---|---|
| `gitnexus-cli` | `~/.claude/skills/gitnexus-cli/` | You need to analyze, index, inspect, clean, or document a GitNexus graph. | Claude/Codex: **P**; Gemini/Antigravity: `UNKNOWN` |
| `gitnexus-debugging` | `~/.claude/skills/gitnexus-debugging/` | You need to trace a bug, error, or failing behavior. | Claude/Codex: **P**; Gemini/Antigravity: `UNKNOWN` |
| `gitnexus-exploring` | `~/.claude/skills/gitnexus-exploring/` | You need to understand architecture, execution flow, or unfamiliar code. | Claude/Codex: **P**; Gemini/Antigravity: `UNKNOWN` |
| `gitnexus-guide` | `~/.claude/skills/gitnexus-guide/` | You need help using GitNexus itself. | Claude/Codex: **P**; Gemini/Antigravity: `UNKNOWN` |
| `gitnexus-impact-analysis` | `~/.claude/skills/gitnexus-impact-analysis/` | You need to assess dependencies or risk before changing code. | Claude/Codex: **P**; Gemini/Antigravity: `UNKNOWN` |
| `gitnexus-refactoring` | `~/.claude/skills/gitnexus-refactoring/` | You need a safe rename, extraction, move, split, or restructure. | Claude/Codex: **P**; Gemini/Antigravity: `UNKNOWN` |
| `idea-pressure-tester` | `~/.skills/idea-pressure-tester/` | You want to score or pressure-test a new idea. | Claude/Codex: **P**; Gemini/Antigravity: `UNKNOWN` |
| `new-project-kickstart` | `~/.skills/new-project-kickstart/` | You are starting a new creative project and need its foundation. | Claude/Codex: **P**; Gemini/Antigravity: `UNKNOWN` |
| `past-chat-archaeologist` | `~/.skills/past-chat-archaeologist/` | You need a prior decision, artifact, or conversation result. | Claude/Codex: **P**; Gemini/Antigravity: `UNKNOWN` |
| `session-handoff` | `~/.skills/session-handoff/` | You are wrapping up and need a compact handoff. | Claude/Codex: **P**; Gemini/Antigravity: `UNKNOWN` |
| `startday` | `~/.skills/startday/` | You want the morning brief or today's orientation. | Claude/Codex: **P**; Gemini/Antigravity: `UNKNOWN` |

## Shelf skills

These are deliberately explicit-only in Claude Code and Codex. Use their names
when you want the exact workflow; that keeps their descriptions out of the
always-loaded budget.

| Skill | Location | Use it when | AI |
|---|---|---|---|
| `abcde` | `~/.skills/abcde/` | You want short guided A/B/C/D/E clarification. | Claude/Codex: **S**; Gemini/Antigravity: `UNKNOWN` |
| `audio-drama-formatter` | `~/.claude/skills/audio-drama-formatter/` | You need an ElevenLabs-ready audio drama or podcast-fiction script. | Claude/Codex: **S**; Gemini/Antigravity: `UNKNOWN` |
| `bandwidth-snapshot` | `~/.skills/bandwidth-snapshot/` | You want a daily planning snapshot or a planned-versus-actual review. | Claude/Codex: **S**; Gemini/Antigravity: `UNKNOWN` |
| `brand-voice` | `~/.skills/brand-voice/` | You need Human-AI Integration public content, posts, hooks, or bio copy. | Claude/Codex: **S**; Gemini/Antigravity: `UNKNOWN` |
| `byteworks-comic-script` | `~/.skills/byteworks-comic-script/` | You need a four-panel ByteWorks / Botsly comic script. | Claude/Codex: **S**; Gemini/Antigravity: `UNKNOWN` |
| `confirm-suspicions` | `~/.skills/confirm-suspicions/` | You want a real-output QA gate and rollback plan. | Claude/Codex: **S**; Gemini/Antigravity: `UNKNOWN` |
| `edit-article` | `~/.skills/edit-article/` | You need an article restructured, clarified, or tightened. | Claude/Codex: **S**; Gemini/Antigravity: `UNKNOWN` |
| `eternal-witness` | `~/.skills/eternal-witness/` | A completed session produced a reusable procedure worth preserving as a skill. | Claude/Codex: **S**; Gemini/Antigravity: `UNKNOWN` |
| `expedition-map` | `~/.skills/expedition-map/` | You need to map an unfamiliar codebase before changing it. | Claude/Codex: **S**; Gemini/Antigravity: `UNKNOWN` |
| `grill-me` | `~/.skills/grill-me/` | You want a plan or design stress-tested through relentless questions. | Claude/Codex: **S**; Gemini/Antigravity: `UNKNOWN` |
| `horror-voice` | `~/.skills/horror-voice/` | You are writing horror fiction and need the shared craft rules. | Claude/Codex: **S**; Gemini/Antigravity: `UNKNOWN` |
| `parody-brand` | `~/.skills/parody-brand/` | You want a new parody-brand package: concept, voice, products, and script. | Claude/Codex: **S**; Gemini/Antigravity: `UNKNOWN` |
| `preordain` | `~/.skills/preordain/` | You need a narrative PR description from the current diff. | Claude/Codex: **S**; Gemini/Antigravity: `UNKNOWN` |
| `spell-pierce` | `~/.skills/spell-pierce/` | You want adversarial edge-case testing before shipping. | Claude/Codex: **S**; Gemini/Antigravity: `UNKNOWN` |
| `teferis-protection` | `~/.skills/teferis-protection/` | You are about to take a destructive or stateful CLI action and need guardrails. | Claude/Codex: **S**; Gemini/Antigravity: `UNKNOWN` |

## Maintenance loop

1. Edit the canonical `SKILL.md` rather than a symlinked copy.
2. Keep the first sentence concrete: what the skill does and when to use it.
3. Decide **P** only for skills the agent truly needs to notice on its own;
   otherwise use **S**.
4. For Claude, set `disable-model-invocation: true` to shelf a skill. For
   Codex, add `agents/openai.yaml` with
   `policy.allow_implicit_invocation: false`.
5. Run the audit and inspect `docs/OVERLAP-REVIEW.md` before merging similarly
   named workflows.

## Boundaries and known gaps

- The audit is static: it checks files, metadata, routing language, paths, and
  budgets. It does not prove an agent triggered the right skill.
- Gemini and Antigravity do not expose the same documented shelf state used by
  Claude Code and Codex. Their `UNKNOWN` label is intentional.
- Claude Desktop plugins are not this filesystem skill library. They are
  account-level plugins managed in Claude Desktop under **Customize → Plugins**.
  The Desktop plugin list was empty when this snapshot was made. A Desktop
  plugin/local-extension wrapper is required before it can expose a shared
  `SKILL.md` such as `pkos-ingest`.
