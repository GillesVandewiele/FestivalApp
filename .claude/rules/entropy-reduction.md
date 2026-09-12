# Entropy reduction

Agents produce code faster than anyone can read it, so keeping the shape of the repository
flat matters more than usual.

- **Lines of code is not a metric in either direction.** Code golf is as wrong as verbose
  expansion. Clarity is the goal.
- **Delete aggressively.** If something is clearly unused, remove it. Git remembers.
- **Three similar functions beat a premature abstraction.** Reach for the abstraction on
  the third caller, not the first.
- **Never refactor existing code without asking first.** What looks like debt may be a
  deliberate trade-off.
- **Files that change together live together.** Split by responsibility, not by layer.

When this seems to conflict with `CLAUDE.md` or a direct instruction from the user, they
win.
