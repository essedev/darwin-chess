# Roadmap

## Current state

The experiment has been running 24/7 on the server since 25 November: agent at high effort, referee, Lichess bot on the reigning champion and the public site on darwin.esse.dev. At the end of the day the champion is gen-8, about 1,490 Elo against Stockfish (± 115). It is updated with `make deploy` without interrupting the session and the game. The history is in `CYCLES.md`.

## Milestones

- [ ] **Lichess playing again**: Lichess answers 429 to challenges without saying how long to wait, and the bot has not played since 19:59. The backoff up to 4 hours is in production: if challenges do not resume, find out which limit triggers (challenges per bot, per day) and tune `DARWIN_LICHESS_CHALLENGE_EVERY_S` or rely on incoming challenges.
- [ ] **High effort on trial** (per DECISIONS #25): after a day, cost per session and yield of the submissions at `high` against those at `low`; back to `medium` if the cost rises a lot with no benefit.
- [ ] **Tuning the server**: a one-hour load test to tune cores and parallel games (the Air has no fan). The referee is the bottleneck, not the budget: the budget of the 25th was less than 10% used.
- [ ] **M6 Opening book**: a book filtered by Stockfish instead of the random one the referee generates (per DECISIONS #10). The anchor ladder is already done.
