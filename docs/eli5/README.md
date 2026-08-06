# The friendly guide to AI skill booklets

Welcome! This is a guide for a curious kid, a tired grown-up, or anyone who
does not want a pile of computer words thrown at them.

## The big idea

Imagine you have several robot helpers. One is named Claude, one is Codex, one
is Gemini, and one is Antigravity. They all read booklets from the same shelf in
your house.

There is a fifth helper, Claude Desktop. It reads booklets from a shelf in the
*cloud* instead. If you fix a booklet on the shelf in your house, that fifth
helper still has the old one — you have to fix its copy too.

Each robot can learn special jobs from tiny instruction booklets called
**skills**. One booklet might say, “help plan a day.” Another might say, “help
check code.” A skill is not the robot itself. It is more like a recipe the robot
can follow when the recipe fits the job.

`skill-audit` is the careful librarian. It looks at the booklets and says:

> “Are these booklets easy to find, easy to understand, and not getting in one
> another’s way?”

It does not change the booklets. It only makes a report.

If you want the grown-up technical map of the same idea, see
[The skill-library model](../library-model.md). This friendly guide explains the
same three questions with fewer vendor-specific details.

## Where the real booklets live

Your personal, shared booklets live in one main home:

```text
~/.skills/
```

The funny `~` means “your own home folder.” Think of `~/.skills/` as a library
shelf in your bedroom.

Claude’s shelf has **shortcuts** to those same books. A shortcut is called a
**symlink**, but “shortcut” is the only word you need to remember. The other
shared robot shelves lead through Claude’s shelf too:

```text
~/.skills/                 the real personal books
        ↑
~/.claude/skills/           shortcuts to those books
        ↑
~/.agents/skills/           a shortcut to Claude's shelf
        ↑
~/.gemini/config/skills/       Antigravity's documented global shelf
```

This is useful because you change one real booklet instead of trying to repair
four copies. If you improve a recipe for cookies, every robot reading the
shortcut gets the improved recipe.

Some skills belong to the robot app itself. Those bundled or runtime-managed
skills stay in the app’s own place, such as `~/.codex/skills/`. We do not move
those into the personal library, because the app may need to update or manage
them itself.

## Backpack books and shelf books

Robots have limited “thinking backpack” space. They cannot carry every booklet
open all day.

| Name in the report | Kid version | What it means |
|---|---|---|
| **POCKET** | In the backpack | The robot may notice and use this skill by itself. Its label is carried into every chat—usually name plus description, or only the name when Claude is set to `name-only`. |
| **SHELF** | On the bookshelf | The robot waits for you to name the skill or clearly ask for its special job. |
| **UNKNOWN** | We cannot see inside this backpack | The robot’s app does not give the librarian a trustworthy way to tell whether the skill is automatic or explicit-only. |
| **DISABLED** | The cupboard is locked | The robot app has switched this skill off, so it cannot use it until someone turns it back on. |

Pocket skills are handy, but too many make the backpack heavy. Shelf skills are
still real and useful—they simply wait until you ask for them. A disabled skill
is different: asking by name will not work until the app turns it back on.
Gemini tells the audit whether a book is enabled or disabled, but it has no
middle “shelf” choice. Antigravity still keeps that part of its backpack hidden.

For example, a daily helper such as `startday` may make sense in a backpack.
A very special helper such as `grill-me` can stay on the shelf until you say,
“Use `grill-me` to challenge my plan.”

## What makes a good booklet?

The first little description on a skill is like a label on a drawer. A good
label says both **what is inside** and **when to open it**.

Good label:

> “Check a release for regressions. Use after deploying a release.”

Not-so-good label:

> “Helps with things.”

The librarian checks whether a label is missing, too tiny, too long, or too
blurry. It also checks that the label says when the robot should use the skill.
That is important because a brilliant 100-page booklet cannot help if the robot
never knows to open it.

## How the librarian looks for mix-ups

Sometimes two booklets may be trying to help with almost the same job. That can
make a robot unsure which one to choose.

The librarian does **not** read minds. It uses a simple word game:

1. It reads the short labels on two skills.
2. It ignores tiny and very common words like “use,” “when,” and “help.”
3. It looks for meaningful words or quoted trigger phrases that appear in both.
4. It raises its hand when it finds enough shared words.

So an overlap warning means:

> “These two booklets might be too similar. Please have a human read both.”

It does **not** mean:

> “These booklets are definitely fighting.”

Two skills can share a perfectly good phrase on purpose. Two skills can also
give opposite instructions using completely different words. The librarian sees
only the first kind of clue, so a person makes the final decision.

## A tiny story

Suppose there are two skills:

- `pizza-helper`: “Make a pizza plan. Use when the user wants dinner ideas.”
- `dinner-helper`: “Plan family meals. Use when the user wants dinner ideas.”

Both labels contain the same quoted phrase, “wants dinner ideas.” The librarian
will flag them for a grown-up to compare.

The grown-up might decide:

- Keep both, but make one say “pizza only” and the other say “a whole week.”
- Put one on the shelf.
- Or join them into one bigger meal-planning booklet.

The librarian points at the possible puzzle. It does not throw away either
booklet.

## How to ask the librarian for help

The grown-up command is:

```sh
python3 skill_audit.py
```

That makes a report. A stricter version is:

```sh
python3 skill_audit.py --strict
```

The strict version treats warnings as a “please fix this before we call it
tidy” signal. It is useful before a big cleanup or a team check-in.

The report can say things such as:

| Report message | Plain-English meaning |
|---|---|
| `broken_symlink` | A shortcut points at a book that is gone. |
| `name_collision` | Two different books have the same title. |
| `missing_description` | A booklet has no useful label. |
| `mode_disagreement` | Claude and Codex were told different backpack/shelf rules. |
| `overlap` | Two labels share enough important words to deserve a look. |
| `budget_exceeded` | A robot’s backpack has too many label words in it. |

## Rules for safe tidying

1. Keep one real personal booklet in `~/.skills/`.
2. Use shortcuts instead of making copies.
3. Give every booklet a clear label: what it does and when to use it.
4. Put only truly helpful everyday skills in the backpack.
5. Read both booklets before changing anything because of an overlap warning.
6. Test a real robot chat after changing a Pocket skill. A tidy label is good,
   but the robot still needs to show that it picks the right booklet.

## Where to go next

- [skill-audit.md](skill-audit.md) — a tiny explanation of the librarian.
- [skill-wiki.md](skill-wiki.md) — a tiny explanation of the inventory list.
- [skill-handbook.md](skill-handbook.md) — choose the current skills by job,
  with kid-friendly example requests.
- [../living-manual.md](../living-manual.md) — the detailed grown-up manual.
- [../HAPPYPATH.md](../HAPPYPATH.md) — the grown-up cleanup checklist.

The most important thing to remember is this: one real book, clear labels, and
shortcuts for sharing. That keeps the robot library neat without making it
boring.
