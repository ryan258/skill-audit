# ELI5: skill-wiki

Imagine `skill-wiki` as the **master inventory list and rulebook** for all the instruction booklets (skills) on your computer.

Here is the simple breakdown of what it explains:

## 1. 🔗 "One Master Copy" Rule (Magic Shortcuts)
Instead of writing separate copies of the same personal booklet for several AI
apps ([Claude Code](https://docs.anthropic.com/en/docs/agents-and-tools/claude-code/overview), [Codex](https://openai.com), [Gemini CLI](https://gemini.google.com), [Antigravity](https://antigravity.google)), you write **one master booklet**. Then, you create "magic shortcuts" (symlinks) so the apps can reach that same book. The audit can see the shortcuts; a real app inventory or chat is still needed to prove an app loaded it.

## 2. 🎒 Pocket vs. 🧹 Shelf

The wiki splits all your booklets into two groups:

* **Pocket Skills (P) — 🎒 In the Backpack**: 
  - These are the skills the AI carries around **all day long**. 
  - The AI reads their descriptions every time you start a chat, so it can **automatically** step in when you need help (e.g., `startday`, `session-handoff`, `gitnexus`).
  - *Catch:* Carrying too many heavy books makes the backpack too heavy (context budget)!

* **Shelf Skills (S) — 🧹 High Up on the Shelf**:
  - These skills stay on a shelf in the closet.
  - The AI doesn't carry them around, so they don't clog up memory. 
  - To use them, you must **ask for them by name** (e.g., *"Hey AI, go get `grill-me` off the shelf!"*).

## 3. 🤖 The 4 AI Friends
- **[Claude Code](https://docs.anthropic.com/en/docs/agents-and-tools/claude-code/overview) & [Codex](https://openai.com)**: Very clear about which books are in their pocket vs. on their shelf.
- **[Gemini CLI](https://gemini.google.com) & [Antigravity](https://antigravity.google)**: They can read all the books, but they don't publicly announce if a book is in their pocket or on their shelf (so their status is marked **`UNKNOWN`**).

## 4. 📋 The Master Inventory List
It lists every single booklet on your machine (like `gitnexus-cli`, `startday`, `grill-me`, `pkos-ingest`), showing:
- Where the master copy lives.
- When to use it.
- Whether it lives in the **Pocket (P)** or on the **Shelf (S)**.

---

**In short:** The `skill-wiki` is your cheat-sheet showing **where every skill lives**, **which skills the AI carries automatically**, and **which skills you have to call out by name**.
