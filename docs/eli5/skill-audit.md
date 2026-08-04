# ELI5: skill-audit

Imagine you have a team of **AI helpers** (like [Claude Code](https://docs.anthropic.com/en/docs/agents-and-tools/claude-code/overview), [Codex](https://openai.com), [Gemini CLI](https://gemini.google.com), and [Antigravity](https://antigravity.google)) and a giant box of **instruction booklets** (called "skills") that teach them special tricks—like writing code, checking grammar, or drawing maps.

`skill-audit` is like a **smart librarian** for those booklets. Here is what it does:

## 1. 🔍 Checks the shelves it knows about
It checks the usual places where your AI helpers keep their instruction manuals,
plus any project shelf you ask it to inspect. It does not magically search every
file on your whole computer.

## 2. 🕵️‍♂️ Looks for mistakes
It checks each booklet for problems:
- **Broken pages**: Typos or bad formatting in the instructions.
- **Missing rules**: Booklets that forget to explain *when* the AI should use them.
- **Too long**: Booklets that are too giant to fit nicely into the AI's memory.

## 3. 👯 Finds duplicate & overlapping tricks
If you have two booklets with the exact same name, it points them out. It also
looks for labels that share important words or the same quoted trigger phrase.
That second check is a clue for a person to read—not proof that two booklets do
the exact same job.

## 4. 🧠 Keeps track of "Brain Space" (Context Budget)
If an AI helper loads too many booklets at the start of every chat, its "brain" gets cluttered. `skill-audit` measures how much memory your active booklets use and warns you if they're taking up too much room.

## 5. 🛡️ Safe & Read-Only
It acts like a reader, **never an editor**. It only *looks* at your files to give you a report card—it will never change or delete any of your work!

---

**In short:** `skill-audit` is a read-only inspection script that helps keep
your AI skill library clean, organized, and easier to understand.
