# The kiddo handbook: choosing an AI skill

This book is for choosing the right helper without needing to memorize computer
words. It covers **21 canonical personal skills plus six locally installed
GitNexus helpers** in the current library.
Bundled robot-app skills are not listed here because they belong to the app,
not to this personal skill shelf.

## First rule: say what you want

You usually do **not** have to know a skill’s name. Start by saying the job:

> “Help me understand this confusing project.”

Some skills ride in the robot’s backpack and may be noticed automatically.
Others live on the shelf. For a shelf skill, it is best to say its name too:

> “Use `spell-pierce` to look for sneaky problems before we ship.”

There is no penalty for asking plainly. The name is a shortcut, not a secret
password.

## The choose-your-adventure map

```text
Want to start or finish your day?        -> startday / bandwidth-snapshot / session-handoff
Need to find an old decision?            -> past-chat-archaeologist
Have a new idea or project?              -> idea-pressure-tester / new-project-kickstart
Need to understand or change code?       -> GitNexus helpers / expedition-map
Want to test or protect a code change?   -> confirm-suspicions / spell-pierce / teferis-protection
Want to write something?                 -> brand-voice / edit-article / creative helpers
Need to save files into PKOS?            -> pkos-ingest
Need help choosing a direction?          -> abcde / grill-me
```

## Backpack helpers

These skills are marked **Pocket** for Claude Code and Codex. The robot may
consider them automatically when your request matches. You can still name one
if you want to be extra clear.

| Helper | Ask it for this | Example words to use |
|---|---|---|
| `startday` | A morning brief or help seeing today clearly. | “Start my day. What is on my agenda?” |
| `session-handoff` | A neat note for the next person—or tomorrow-you—when a work session ends. | “Use `session-handoff` and tell future me where we stopped.” |
| `past-chat-archaeologist` | A decision, plan, or thing made in an earlier chat. | “Find what we decided about the launch plan last time.” |
| `idea-pressure-tester` | A tough-but-fair score before deciding to build an idea. | “Pressure-test my homework-planning app idea before I commit.” |
| `new-project-kickstart` | The first building blocks after deciding to make a creative project. | “I’m making the spooky comic; help me kick off the project.” |
| `gitnexus-cli` | A command for working with a GitNexus code map. | “Use `gitnexus-cli` to inspect this project’s graph.” |
| `gitnexus-debugging` | Finding why code is broken. | “This button is broken. Help me trace the bug.” |
| `gitnexus-exploring` | Learning how unfamiliar code fits together. | “Show me how this app works before we touch it.” |
| `gitnexus-guide` | Learning how to use GitNexus itself. | “How do I use GitNexus to find a function?” |
| `gitnexus-impact-analysis` | Checking what might break before a code change. | “What could break if we change the login rule?” |
| `gitnexus-refactoring` | Safely tidying code without changing what it does. | “Help me split this giant file safely.” |

### The six GitNexus friends

They have very similar names, so here is the easiest way to choose:

| If you are thinking… | Pick… |
|---|---|
| “What does this code do?” | `gitnexus-exploring` |
| “Why is this code broken?” | `gitnexus-debugging` |
| “What will break if I change this?” | `gitnexus-impact-analysis` |
| “How do I rename or split this safely?” | `gitnexus-refactoring` |
| “How do I use the GitNexus tool?” | `gitnexus-guide` |
| “Run a GitNexus command for me.” | `gitnexus-cli` |

## Shelf helpers

These skills are marked **Shelf** for Claude Code and Codex. Tell the robot the
name when you want their special recipe.

### Planning and decisions

| Helper | What it is good at | Say this |
|---|---|---|
| `abcde` | Giving you small A/B/C/D/E choices instead of a giant confusing question. | “Use `abcde` to help me choose a project idea.” |
| `bandwidth-snapshot` | Seeing how much time and energy you really have. | “Use `bandwidth-snapshot` to compare my plan with what I got done.” |
| `grill-me` | Asking lots of hard questions to test a plan. | “Use `grill-me` and challenge my lemonade-stand plan.” |

`abcde` is for choosing among friendly little options. `grill-me` is for when
you want a coach to poke every weak spot in the plan. They can both help with a
decision, but they have different moods.

### Building, testing, and staying safe

| Helper | What it is good at | Say this |
|---|---|---|
| `confirm-suspicions` | Checking real output and making a “how to undo it” plan. | “Use `confirm-suspicions` to check whether this export really works.” |
| `expedition-map` | Drawing a map of unfamiliar code before changing it. | “Use `expedition-map` to map this project first.” |
| `preordain` | Writing a clear pull-request story about a code change. | “Use `preordain` to write the PR description from this diff.” |
| `spell-pierce` | Looking for sneaky edge cases before shipping. | “Use `spell-pierce` to find weird ways this form could fail.” |
| `teferis-protection` | Pausing before a powerful command that could change or delete things. | “Use `teferis-protection` before I run this database command.” |
| `eternal-witness` | Turning a useful finished-session recipe into a reusable skill. | “Use `eternal-witness` to save this repeatable process as a skill.” |

Use `confirm-suspicions` when you want proof from a real result and a rollback
plan. Use `spell-pierce` when you want someone to imagine tricky failure cases.
Use `teferis-protection` before a command that can change important stuff.

### Writing and making things

| Helper | What it is good at | Say this |
|---|---|---|
| `brand-voice` | Public writing in the Human-AI Integration voice. | “Use `brand-voice` to write a post about helpful robots.” |
| `edit-article` | Making an article clearer, better organized, and less wobbly. | “Use `edit-article` to make this school article easier to read.” |
| `audio-drama-formatter` | Formatting an audio drama or fiction podcast script for ElevenLabs. | “Use `audio-drama-formatter` to format this scene.” |
| `byteworks-comic-script` | Writing a four-panel ByteWorks/Botsly comic. | “Use `byteworks-comic-script` to make a comic about a runaway toaster bot.” |
| `horror-voice` | Writing scary fiction with the shared horror craft rules. | “Use `horror-voice` to help make this ghost story creepier.” |
| `parody-brand` | Inventing a funny pretend brand: its idea, voice, products, and script. | “Use `parody-brand` to invent a silly brand for moon-flavored cereal.” |

`brand-voice` uses one existing public voice. `parody-brand` invents a whole new
funny brand. `edit-article` improves writing you already have. The comic and
horror helpers are special creative playgrounds.

### Keeping memories and files safe

| Helper | What it is good at | Say this |
|---|---|---|
| `pkos-ingest` | Carefully saving local files, notes, folders, and certain ZIPs into PKOS. | “Use `pkos-ingest` to preserve these notes in PKOS.” |

PKOS is like a careful archive room. Use this helper when you want files saved
with their history, not when you simply want to open a file and read it.

## Three tiny practice games

### Game 1: The confusing code castle

You find a giant code project and do not know where the drawbridge is.

1. Say: “Help me understand this codebase before we change anything.”
2. Try `gitnexus-exploring` or `expedition-map`.
3. Before changing a bridge, try `gitnexus-impact-analysis`.
4. Before shipping, try `spell-pierce`.

### Game 2: The big creative idea

You want to make a spooky robot comic.

1. Try `idea-pressure-tester` to see whether the idea has strong legs.
2. Try `new-project-kickstart` to give the project a beginning.
3. Try `horror-voice` for scary-story rules.
4. Try `byteworks-comic-script` if it is a ByteWorks/Botsly four-panel comic.

### Game 3: The scary big button

You are about to run a command that might change lots of files.

1. Stop and read the command.
2. Say: “Use `teferis-protection` before I run this.”
3. If the change makes an output, use `confirm-suspicions` to check it.
4. Write down what happened with `session-handoff` when you finish.

## A few important grown-up truths

- A skill is helpful advice, not magic. Check important work.
- A Pocket label means “may be considered,” not “guaranteed to run.”
- Gemini tells the librarian which books are enabled (`POCKET`) or switched off
  (`DISABLED`), but it has no middle shelf choice. Antigravity still says
  `UNKNOWN` because the librarian cannot read that app's backpack rule.
- `DISABLED` means the app has switched the skill off; naming it will not work
  until that host setting is changed.
- If two skills sound alike, that is a reason to read both, not a reason to
  delete one.
- `skill-audit` reads and reports; it does not repair or delete your skills.

## Your next page

Go back to the [friendly guide](README.md) to learn about the library shelves,
or read the [skill wiki](../skill-wiki.md) when you want the grown-up list of
locations and settings.
