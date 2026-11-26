# Backlog

Open work nobody is about to do, by area, in no order. What is planned next is in `ROADMAP.md`.

## Referee

- **Stale candidates**: since gen-8, 6 of 17 iterations ended `stale`: the agent prepared its candidate while another was on trial, and the change no longer applied on top of the new champion. It is now the main source of lost work, ahead of rejections (none). To resume: read the conflicts of experiments 27, 30, 32, 35, 38 and 42 (real overlaps on the same code, or a reapplication stricter than it needs to be) before choosing a remedy.
- **Joint Elo fit** (per DECISIONS #29): the evidence fits the logistic model with more spread than it assumes (chi-square 33 over 19 degrees of freedom on 26 November). Recheck as the chain grows; if the misfit grows, consider discounting the self-play gains or weighing the matches by their pentanomial variance.
