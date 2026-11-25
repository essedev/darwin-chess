---
paths:
  - "*.md"
  - "docs/**/*.md"
---
- Docs in English. `README.it.md` mirrors `README.md` in the same commit, in Italian with real accented letters, never an apostrophe instead of an accent.
- No em dashes, no emoji, no section sign (write `#4.a`).
- Docs and code in the same commit: if behaviour changes, update the file that describes it.
- No numbers the repository can compute (counts of files, lines, tests): they go stale.
- `seed/*.md` is in English: it enters the agent's prompt.
