# The skill-library model

Read this first. A personal skill library has three separate questions. Keeping
them separate makes the rest of the documentation easier to use.

```text
1. Source of truth       ~/.skills/<skill>/SKILL.md        your account
                                  |                              |
                                  | symlink or vendor link       | app sync
                                  v                              v
2. Tool discovery        Claude / Codex / Gemini /        Claude Desktop
                         Antigravity find the skill       caches the skill
                                  |                              |
                                  | each tool applies its own collision rules
                                  v                              v
3. Invocation state      POCKET, SHELF, UNKNOWN, or DISABLED for that tool
```

Those are **two libraries**, and the left one does not feed the right one.

The arrows show the usual lifecycle, not a universal vendor implementation.
One physical personal skill can be discovered by several tools, and its
invocation mode can differ by tool. Bundled and runtime-managed skills stay in
their tool-managed locations; they are not part of the personal source folder.

## 1. One source of truth — per library

Personal skills live in `~/.skills/`. A tool-facing directory should link to
that copy rather than hold a second `SKILL.md`. This prevents edits from
drifting between tools.

That rule governs the **local** library only. Claude Desktop reads a second
library that syncs from your account, including Anthropic's own built-ins, and
`~/.skills/` is not its source. This is vendor-documented: the Claude Code docs
state that Cowork and cloud sessions "don't read `~/.claude/skills/` on your
machine" and instead "load the skills enabled for your claude.ai account, synced
at session start". The on-disk cache path the audit scans remains an observation. Editing a skill in `~/.skills/` does **not**
change Desktop's copy; that is done in the app (`Settings -> Skills -> the skill
-> Replace`). A skill can therefore exist in both libraries and legitimately
differ — a runtime path is the usual reason, since Desktop writes to
`/mnt/skills/user/` where the local library writes to `~/.skills/`. Because the
two are never offered to a model at the same time, the audit scopes every
skill-to-skill comparison to one library: a shared name is the two libraries
agreeing, not a collision.

`skill_audit.py` resolves links and reports a linked skill once, with every
place from which it is reachable. Two different real directories with the same
skill name are a collision, not useful redundancy.

## 2. Discovery and collision resolution

Discovery answers “can this tool see the skill?” Collision resolution answers
“which copy wins if it can see more than one?” They are not the same question.

| Tool | Rule represented by the audit | If no rule resolves it |
|---|---|---|
| Claude | `enterprise > personal > project`; enterprise is not visible on disk to the audit. | Equal project/nested paths are an undeterminable tie. |
| Gemini | `workspace > user > extension > built-in`; within a tier, `.agents` over `.gemini` is observed rather than vendor-documented. | No winner is reported. |
| Codex | No precedence rule is assumed. | Both entries are reported and the user chooses. |
| Antigravity | The audit reports discovered paths but cannot establish a complete vendor precedence model. | Treat collisions as needing manual review. |
| Claude Desktop | A separate account-synced library; names are unique server-side, so no cross-copy precedence applies. | Not applicable — it never competes with the local library. |

A copy marked `DISABLED` does not compete or win for that host. It remains in
the collision evidence because another host or workspace may still enable it.

The detailed per-tool commands and path caveats are in
[skill-setup.md](../skill-setup.md). The audit's exact discovery and precedence
behavior is in [living-manual.md](living-manual.md).

## 3. Invocation mode

After a tool discovers a skill, it may either consider it automatically or wait
for an explicit request:

| Mode | Meaning | Operational choice |
|---|---|---|
| **POCKET** | The tool may invoke the skill on its own; its listing metadata consumes every-session context (normally name plus description, or name only under Claude's `name-only` override). | Reserve for a small number of broadly useful skills the agent must notice. |
| **SHELF** | The tool waits for the user to name the skill or clearly request its specialized job. | Use for deliberate, narrow, or infrequent workflows. |
| **UNKNOWN** | The audit has no readable, valid signal for that tool/context. | Do not infer a mode or include it in known-mode budget math. |
| **DISABLED** | The host explicitly hides or disables the skill, so it cannot be invoked there. | Re-enable it in the host before judging routing or budget. |

Claude and Codex can assign POCKET or SHELF per skill through
`disable-model-invocation` and `policy.allow_implicit_invocation`. Host settings
then take precedence: Claude Code's `skillOverrides` can force `on`, `name-only`,
`user-invocable-only`, or `off`; Codex's `[[skills.config]] enabled = false`
produces DISABLED. Gemini has no SHELF state, but persistent `skills.enabled`
and union-merged `skills.disabled` settings make enabled skills POCKET and
disabled skills DISABLED. A Claude `name-only` entry is POCKET but contributes
only its name to listing-budget math. Claude Desktop has its own equivalent, the
`enabled` flag in the cache's `manifest.json`, which the audit reads rather than
assumes; a skill missing from that manifest is UNKNOWN. Antigravity remains
UNKNOWN because it exposes no readable per-skill state. Gemini and Desktop
listing sizes are reported but not graded: neither has a published budget.

## Where to go next

- Need to build or repair a library? Follow [HAPPYPATH.md](HAPPYPATH.md).
- Need per-tool paths, flags, or verification? Read
  [skill-setup.md](../skill-setup.md).
- Need the exact audit contract? Read [living-manual.md](living-manual.md).
- Writing a new skill? Start from [the exemplar](exemplars/skill-example.md), or
  set up an authoring assistant with the paste-ready instructions for a
  [Claude Project](claude-project-skill-instructions.md), a
  [Custom GPT](custom-openai-gpt-skill-instructions.md), or a
  [Gemini Gem](custom-gemini-skill-instructions.md).
- Need plain-language help using an existing library? Read the
  [friendly guide](eli5/README.md).
