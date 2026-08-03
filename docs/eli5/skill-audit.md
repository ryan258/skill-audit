# ELI5: skill-audit

Imagine you have a team of **AI helpers** (like Claude, Codex, Gemini, and Antigravity) and a giant box of **instruction booklets** (called "skills") that teach them special tricks—like writing code, checking grammar, or drawing maps.

`skill-audit` is like a **smart librarian** for those booklets. Here is what it does:

## 1. 🔍 Scans your whole computer
It checks all the places where your AI helpers keep their instruction manuals to see what skills you have installed.

## 2. 🕵️‍♂️ Looks for mistakes
It checks each booklet for problems:
- **Broken pages**: Typos or bad formatting in the instructions.
- **Missing rules**: Booklets that forget to explain *when* the AI should use them.
- **Too long**: Booklets that are too giant to fit nicely into the AI's memory.

## 3. 👯 Finds duplicate & overlapping tricks
If you have two booklets with the exact same name, or two booklets trying to do the exact same job, it points them out so your AI helpers don't get confused.

## 4. 🧠 Keeps track of "Brain Space" (Context Budget)
If an AI helper loads too many booklets at the start of every chat, its "brain" gets cluttered. `skill-audit` measures how much memory your active booklets use and warns you if they're taking up too much room.

## 5. 🛡️ Safe & Read-Only
It acts like a reader, **never an editor**. It only *looks* at your files to give you a report card—it will never change or delete any of your work!

---

**In short:** `skill-audit` is a quick 1-second inspection script that keeps your AI skill library clean, organized, and running fast!
