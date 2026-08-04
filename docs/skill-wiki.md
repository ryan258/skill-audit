# Skill wiki

Snapshot: 2026-08-04. Regenerated from a live `skill_audit.py` run, not maintained
by hand. It is a reference for what is installed, not a claim that an agent will
select a skill for every matching prompt — that is a routing question, and
`route_check.py` is the tool for it.

For the stable architecture behind this dated inventory, start with
[The skill-library model](library-model.md). It separates canonical storage,
tool discovery, and invocation mode; this page records the current library
against that model.

## Two libraries

The audit sees **78 unique skills across two libraries that never meet**.

| Library | Source of truth | Reaches | Skills |
|---|---|---|---|
| Local | `~/.skills/` (plus tool-managed dirs like `~/.codex/skills/.system/`) | Claude Code, Codex, Gemini CLI, Antigravity | 58 |
| Claude Desktop | Your claude.ai account, synced into an app-managed cache | Claude Desktop, Cowork, cloud sessions | 20 |

Editing `~/.skills/` does **not** change the Desktop copy. That is vendor
documented: Cowork and cloud sessions do not read `~/.claude/skills/`; they load
the skills enabled for your account. Change a Desktop skill in the app —
Settings → Skills → the skill → Replace.

A name in both libraries is the two agreeing, not a collision. The audit scopes
every skill-to-skill comparison to one library for that reason.

## What is installed where

| Location scanned | Status |
|---|---|
| `~/.claude/skills` | present |
| `~/.agents/skills` | present |
| `~/.codex/skills` | present |
| `/etc/codex/skills` | not present |
| `~/.agents/skills` | present |
| `~/.gemini/skills` | present |
| `~/.gemini/config/skills` | present |
| `~/Library/Application Support/Claude/local-agent-mode-sessions/skills-plugin/cc52c265-16cd-4207-8284-a9e636896095/3a84a9f6-b1ff-4955-ae36-90c702c3425d/skills` | present |
| `~/.gemini/antigravity/skills` | not present |
| `~/.gemini/antigravity-cli/skills` | not present |

## Budgets

| Listing | Total | Limit | State |
|---|---|---|---|
| Claude | 1993 | 2000 | pass |
| Codex | 3873 | 4000 | pass |
| Claude Desktop | 7405 | none published | not measured |

Only POCKET skills are charged. `32` skills are pocket in at least one tool.

## Reading the entries

- **POCKET** — eligible for automatic use; its description is loaded every session.
- **SHELF** — invoke by name or with an explicit request for its job.
- **UNKNOWN** — Gemini and Antigravity expose no documented shelf signal. Do not
  infer that a listed skill is automatic.
- Claude Desktop's mode comes from the `enabled` flag in its cache manifest.

## Pocket skills — local library (17)

These are charged to the Claude and Codex listing budgets every session.

| Skill | Canonical location | Use it when |
|---|---|---|
| `dhp-context-sync` | `~/.skills/dhp-context-sync` | Use when the user asks to sync, restore, or check session context. |
| `gitnexus-cli` | `~/.skills/gitnexus-cli` | Use when the user needs to run GitNexus CLI commands like analyze/index a repo, check status, clean the index, generate a wiki, or list indexed repos. |
| `gitnexus-debugging` | `~/.skills/gitnexus-debugging` | Use when the user is debugging a bug, tracing an error, or asking why something fails. |
| `gitnexus-exploring` | `~/.skills/gitnexus-exploring` | Use when the user asks how code works, wants to understand architecture, trace execution flows, or explore unfamiliar parts of the codebase. |
| `gitnexus-guide` | `~/.skills/gitnexus-guide` | Use when the user asks about GitNexus itself — available tools, how to query the knowledge graph, MCP resources, graph schema, or workflow reference. |
| `gitnexus-impact-analysis` | `~/.skills/gitnexus-impact-analysis` | Use when the user wants to know what will break if they change something, or needs safety analysis before editing code. |
| `gitnexus-refactoring` | `~/.skills/gitnexus-refactoring` | Use when the user wants to rename, extract, split, move, or restructure code safely. |
| `idea-pressure-tester` | `~/.skills/idea-pressure-tester` | Use when Ryan asks to pressure-test or score a new idea. |
| `imagegen` | `~/.codex/skills/.system/imagegen` | Use when creating, editing, or transforming bitmap visuals such as photos, illustrations, textures, sprites, or mockups. |
| `new-project-kickstart` | `~/.skills/new-project-kickstart` | Use when Ryan says 'new project', 'I have an idea', or 'help me build this out'. |
| `openai-docs` | `~/.codex/skills/.system/openai-docs` | Use when the user asks how to build with OpenAI products or APIs, asks about Codex itself or choosing Codex surfaces, needs up-to-date official docume… |
| `past-chat-archaeologist` | `~/.skills/past-chat-archaeologist` | Use when Ryan asks what we built or decided before. |
| `plugin-creator` | `~/.codex/skills/.system/plugin-creator` | Use when Codex needs to create a new personal plugin, add optional plugin structure, generate or update marketplace entries for plugin ordering and av… |
| `session-handoff` | `~/.skills/session-handoff` | Use when Ryan asks to wrap up or summarize the current session. |
| `skill-creator` | `~/.codex/skills/.system/skill-creator` | Use when creating a new skill or updating an existing skill that extends capabilities with specialized knowledge, workflows, or tool integrations. |
| `skill-installer` | `~/.codex/skills/.system/skill-installer` | Use when a user asks to list installable skills, install a curated skill, or install a skill from another repo (including private repos). |
| `startday` | `~/.skills/startday` | Use when Ryan asks to start his day or see today's agenda. |

## Shelf skills — local library (41)

Explicit-only. Naming them is what keeps their descriptions out of the budget.

| Skill | Canonical location | Use it when |
|---|---|---|
| `abcde` | `~/.skills/abcde` | Use when the user says "grill me", "abcde", or wants guided clarification with A/B/C/D/E answer choices. |
| `api-and-interface-design` | `~/.codex/skills/api-and-interface-design` | Use when designing APIs, module boundaries, or any public interface. |
| `audio-drama-formatter` | `~/.skills/audio-drama-formatter` | Use when creating audio plays, radio dramas, or podcast fiction from story ideas. |
| `bandwidth-snapshot` | `~/.skills/bandwidth-snapshot` | Use when Ryan says "run a snapshot", "let's do the snapshot", "what's my bandwidth today", or asks to review how his day went vs. |
| `brand-voice` | `~/.skills/brand-voice` | Use when Ryan asks for posts, hooks, essays, bio copy, or any public-facing content under The Human-AI Integration brand. |
| `browser-testing-with-devtools` | `~/.codex/skills/browser-testing-with-devtools` | Use when building or debugging anything that runs in a browser. |
| `byteworks-comic-script` | `~/.skills/byteworks-comic-script` | Use when Ryan asks for comic strips, new scripts, weekly batches, or character-driven scenarios for Botsly or any ByteWorks employee. |
| `ci-cd-and-automation` | `~/.codex/skills/ci-cd-and-automation` | Use when setting up or modifying build and deployment pipelines. |
| `code-review-and-quality` | `~/.codex/skills/code-review-and-quality` | Use before merging any change. |
| `code-simplification` | `~/.codex/skills/code-simplification` | Use when refactoring code for clarity without changing behavior. |
| `confirm-suspicions` | `~/.skills/confirm-suspicions` | Use when validating that code or a document is actually correct before trusting it — run the build, hit the ports, check the real output, and generate… |
| `context-engineering` | `~/.codex/skills/context-engineering` | Use when starting a new session, when agent output quality degrades, when switching between tasks, or when you need to configure rules files and conte… |
| `debugging-and-error-recovery` | `~/.codex/skills/debugging-and-error-recovery` | Use when tests fail, builds break, behavior doesn't match expectations, or you encounter any unexpected error. |
| `deprecation-and-migration` | `~/.codex/skills/deprecation-and-migration` | Use when removing old systems, APIs, or features. |
| `documentation-and-adrs` | `~/.codex/skills/documentation-and-adrs` | Use when making architectural decisions, changing public APIs, shipping features, or when you need to record context that future engineers and agents … |
| `doubt-driven-development` | `~/.codex/skills/doubt-driven-development` | Use when correctness matters more than speed, when working in unfamiliar code, when stakes are high (production, security-sensitive logic, irreversibl… |
| `edit-article` | `~/.skills/edit-article` | Use when user wants to edit, revise, or improve an article draft. |
| `eternal-witness` | `~/.skills/eternal-witness` | Scan a completed session for a repeatable, non-obvious procedure and mint it into a permanent skill card. |
| `expedition-map` | `~/.skills/expedition-map` | Use when starting on an unfamiliar repo, beginning a large refactor, or unsure which files hold a feature's logic. |
| `frontend-ui-engineering` | `~/.codex/skills/frontend-ui-engineering` | Use when building or modifying user-facing interfaces. |
| `git-workflow-and-versioning` | `~/.codex/skills/git-workflow-and-versioning` | Use when making any code change. |
| `grill-me` | `~/.skills/grill-me` | Use when user wants to stress-test a plan, get grilled on their design, or mentions "grill me". |
| `horror-voice` | `~/.skills/horror-voice` | Use before writing any horror scene, episode, chapter, lyric, or script. |
| `idea-refine` | `~/.codex/skills/idea-refine` | Use when an idea is still vague, when you need to stress-test assumptions before committing to a plan, or when you want to expand options before conve… |
| `incremental-implementation` | `~/.codex/skills/incremental-implementation` | Use when implementing any feature or change that touches more than one file. |
| `interview-me` | `~/.codex/skills/interview-me` | Use when an ask is underspecified ("build me X" without "for whom" or "why now"), when the user explicitly invokes ("interview me", "grill me", "are w… |
| `observability-and-instrumentation` | `~/.codex/skills/observability-and-instrumentation` | Use when adding logging, metrics, tracing, or alerting. |
| `parody-brand` | `~/.skills/parody-brand` | Use when Ryan says "new parody brand", "build out this brand idea", or names a concept that needs a full brand package. |
| `performance-optimization` | `~/.codex/skills/performance-optimization` | Use when performance requirements exist, when you suspect performance regressions, or when Core Web Vitals or load times need improvement. |
| `pkos-ingest` | `~/.skills/pkos-ingest` | Use when the user asks to ingest, import, archive, preserve, capture, or add source material to PKOS, including attached files and local filesystem pa… |
| `planning-and-task-breakdown` | `~/.codex/skills/planning-and-task-breakdown` | Use when you have a spec or clear requirements and need to break work into implementable tasks. |
| `preordain` | `~/.skills/preordain` | Use when finishing a task and preparing to commit, push, or open a pull request. |
| `review-agent` | `~/.codex/skills/.system/review-agent` | Use when another agent delegates review of uncommitted changes, a base-branch diff, a commit, or custom review instructions. |
| `security-and-hardening` | `~/.codex/skills/security-and-hardening` | Use when handling user input, authentication, data storage, or external integrations. |
| `shipping-and-launch` | `~/.codex/skills/shipping-and-launch` | Use when preparing to deploy to production. |
| `source-driven-development` | `~/.codex/skills/source-driven-development` | Use when you want authoritative, source-cited code free from outdated patterns. |
| `spec-driven-development` | `~/.codex/skills/spec-driven-development` | Use when starting a new project, feature, or significant change and no specification exists yet. |
| `spell-pierce` | `~/.skills/spell-pierce` | Use when designing algorithmic logic, parsing user input, handling DB queries, or processing complex API schemas. |
| `teferis-protection` | `~/.skills/teferis-protection` | Use before installing packages, running shell scripts, editing env files, or migrating databases. |
| `test-driven-development` | `~/.codex/skills/test-driven-development` | Use when implementing any logic, fixing any bug, or changing any behavior. |
| `using-agent-skills` | `~/.codex/skills/using-agent-skills` | Use when starting a session or when you need to discover which skill applies to the current task. |

## Claude Desktop library (20)

Synced from your account, including Anthropic's own built-ins. Not served by any
symlink wiring, and not editable from `~/.skills/`.

| Skill | Mode | Use it when |
|---|---|---|
| `bandwidth-snapshot` | POCKET | Use when Ryan says "run a snapshot", "let's do the snapshot", "what's my bandwidth today", or asks to review how his day went vs. |
| `brand-voice` | POCKET | Use when Ryan asks for posts, hooks, essays, bio copy, or any public-facing content under The Human-AI Integration brand. |
| `byteworks-comic-script` | POCKET | Use when Ryan asks for comic strips, new scripts, weekly batches, or character-driven scenarios for Botsly or any ByteWorks employee. |
| `consolidate-memory` | POCKET | Reflective pass over your memory files — merge duplicates, fix stale facts, prune the index. |
| `cthulhu-on-broadway` | POCKET | Use when Ryan asks for a new sketch in this world, references Cthulhu, Hastur, Dottie, or the Elder Sign Theater, or says \"another Broadway sketch. |
| `docx` | POCKET | Triggers include: any mention of 'Word doc', 'word document', '. |
| `horror-voice` | POCKET | Use before writing any horror scene, episode, chapter, lyric, or script. |
| `idea-pressure-tester` | POCKET | Use when Ryan says "pressure test this", "is this a good idea", "score this concept", or shares a new project or business idea he wants critiqued hone… |
| `morning` | POCKET | Use only when the user explicitly asks to run, see, or set up their morning brief, or if they invoke /morning by name. |
| `new-project-kickstart` | POCKET | Use when Ryan starts something new and needs the full build sequence: premise, bible, cast, craft rules, skill file. |
| `past-chat-archaeologist` | POCKET | Use when Ryan asks "did we build this before?", "find that thing we made", "what did we decide about X", or references something that might exist in a… |
| `pdf` | POCKET | Use this skill whenever the user wants to do anything with PDF files. |
| `pptx` | POCKET | Trigger whenever the user mentions \"deck,\" \"slides,\" \"presentation,\" or references a . |
| `schedule` | POCKET | Use when the user says things like \"every day\", \"each morning\", \"remind me in an hour\", \"run this at noon\", or wants to reschedule an existing… |
| `session-handoff` | POCKET | Use when a long work session is ending, when Ryan says "wrap this up", "what did we do today", or "give me a handoff note". |
| `setup-cowork` | POCKET | Guided Cowork setup — install role-matched plugins, connect your tools, try a skill. |
| `spec-builder` | POCKET | Use when Ryan says "write a spec", "spec this", "new spec", "turn this into a spec", "SDD", or "spec-driven". |
| `startday` | POCKET | Use when Ryan says "startday", "start my day", "what's on today", or opens a session and needs to orient before working. |
| `suno-song-creator` | POCKET | Use when users want to create songs with Suno, need lyrics written, want style tag suggestions, or ask for help with Suno's Custom mode. |
| `xlsx` | POCKET | when the user references a spreadsheet file by name or path — even casually (like \"the xlsx in my downloads\") — and wants something done to it or pr… |

## Maintenance loop

1. Edit the canonical `SKILL.md` rather than a symlinked copy — and remember the
   Desktop copy is a separate edit, in the app.
2. Keep the first sentence concrete: what the skill does and when to use it.
3. Choose POCKET only for skills the agent must notice on its own; otherwise SHELF.
4. For Claude, set `disable-model-invocation: true` to shelf a skill. For Codex,
   add `agents/openai.yaml` with `policy.allow_implicit_invocation: false`.
5. Run `python3 skill_audit.py --strict`, then check routing with
   `python3 route_check.py cases/<skill>.jsonl --repeat 3` if the description changed.

## Boundaries and known gaps

- The audit is static: files, metadata, routing language, paths, budgets. It does
  not prove an agent triggered the right skill; `route_check.py` measures that.
- Gemini and Antigravity do not expose a documented shelf state. `UNKNOWN` is
  intentional and is excluded from budget math.
- The Claude Desktop cache path is a macOS observation, not vendor documentation,
  and it is a cache the app owns. A miss means "not synced yet", never "no skills".
- This page is a dated snapshot. Regenerate it rather than editing rows by hand.
