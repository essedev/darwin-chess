# Roadmap

## Current state

The experiment has been running 24/7 on the server since 25 November: agent at high effort, referee, Lichess bot on the reigning champion and the public site on darwin.esse.dev. On 28 November the champion is gen-20, about 2,265 Elo against Stockfish (± 41, joint estimate). It is updated with `make deploy` without interrupting the session and the game. The history is in `CYCLES.md`, the open work nobody is about to do in `BACKLOG.md`.

## Milestones

- [ ] **The agent's changes on trial** (per DECISIONS #25, #26, #27): high effort costs 1-3 cents an iteration against 0.2 at `low`. After gen-15 the yield slowed: of 20 iterations, 5 accepted and 7 rejected (cycle 6). The agent started its first two jobs on 28 November, both lost to our build-path bug, now fixed. Still to judge over the next reflections: whether its jobs finish and one ever trains the network of DECISIONS #1, whether it keeps tools in `/memory` and varies its changes, or keeps applying one textbook technique per session; back to `medium` if the yield fades.
- [ ] **Tuning the server**: a one-hour load test to tune cores and parallel games (the Air has no fan). The referee is the bottleneck, not the budget: the budget of the 25th was less than 10% used.
- [ ] **M6 Opening book**: a book filtered by Stockfish instead of the random one the referee generates (per DECISIONS #10). The anchor ladder is already done.
