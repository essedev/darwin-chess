# Changelog

What is new in the lab, most recent first.

## 0.6.0, 28 November 2026

- **The Lichess games, one by one**: every finished game of the bot has its own page, with the board to step through move by move (the arrow keys work too), the evaluation curve, the inaccuracies, mistakes and blunders marked as Lichess marks them, the move where the game turned and the commentary. Before, the site showed only the last three games and sent visitors to Lichess, where the analysis is missing.
- **Every game, filtered**: the list, grouped by day, filters by generation, result, rated games, the opponent's name, bot or person, and speed. Filters and page stay in the address: coming back from a game finds the list as you left it. It opens from the last games on the live page.
- **The agent's long jobs, with their purpose**: when the agent starts a long job (games against itself, training), it says in one sentence what the job is for. On the live page that sentence sits under its thought, linked to the session that started it; the session's page says how the job ended and, when it went wrong, why. The first two stopped right after the build because of a mistake of ours, now fixed.
- **The bot plays all day**: Lichess challenges are spread over the hours instead of running out in the first five, and an opponent that already played 10 games in a day is declined, so nobody keeps the bot for themselves. A generation's strength on Lichess counts rated games only.
- **Comfortable on a phone too**: no page scrolls sideways any more, the help opens inside the screen and the generation names under the Elo chart no longer overlap.

## 0.5.0, 26 November 2026

- **Watch the agent at work**: every session has its own page with everything the agent does, one action per line in plain words ("reads main.rs", "builds", "plays a test match: 60 games", "waits 15 minutes"). The real command and what came back are a click away; in between, its thoughts and its reasoning, which stays in English. While the session runs the page updates by itself, and at the end it says how it went.
- **No more empty board**: when the referee is not playing, the middle of the live page shows the session in progress, with the action of the moment, a countdown when the agent waits and the latest lines. With a game on, a line under the board says what the agent is doing.
- **Always at hand**: the session opens from the top bar of the live page, from every attempt in Evolution, from the changes on the Code page and from Mind, which shows what the agent is working on right now.

## 0.4.0, 25 November 2026

- **A livelier site**: each thing has its own colour, the same on every page (the champion's strength in blue, the generations in violet, the verdict in green, the spend in amber, what is live in coral).
- **Animated waits**: while data arrives a knight hops across the board, if the lab does not answer the king shakes, when there is nothing yet the pieces walk to their squares.
- **One game at a time**: the live board follows a game from start to end and shows its result before moving on; our engine is always at the bottom, and the match wins go up game by game.

## 0.3.0, 25 November 2026

- **Everything in Italian too**: the agent's live thought, its strategy, its notes and the instructions it receives can be read translated. The English original is a click away; only the code stays as it is.
- **Updates without interruptions**: when the lab is updated, the agent finishes the work in progress and the bot finishes its Lichess game instead of abandoning it.

## 0.2.0, 25 November 2026

The live page and the evolution redesigned to be read at a glance.

- **Short titles**: every attempt by the agent has a title of a few words, in Italian and in English, instead of its whole hypothesis. The full hypothesis stays in the details.
- **An honest Elo**: the champion's strength comes with its margin of error, and the chart shows when two generations cannot be told apart yet. The gain over the previous champion is explained separately.
- **The trial in progress**: while the referee judges a candidate, the live page shows the games played and which way the evidence leans.
- **A live page that does not grow**: three columns of the same height, the last three results and a link to the full history. The site's name is always in the bar.
- **A compact evolution**: generations and experiments in rows that open, with filters by outcome and ten per page.

## 0.1.0, 25 November 2026

The first version: an artificial intelligence writes a chess engine on its own and improves it one generation after another.

- **The agent at work**: a low-cost language model (Claude Haiku) receives an empty engine and builds it. In each session it reads the previous verdict, makes a change and submits it with its hypothesis. Every ten sessions it stops to reflect and rewrites its own strategy.
- **A referee that cannot be fooled**: every change is built, checked against the rules of chess and put to the test in hundreds of games against the reigning champion. It becomes the new generation only if it wins with statistical certainty. The agent can neither see nor touch the referee.
- **The measure against Stockfish**: every new champion plays Stockfish at limited strength, to estimate its absolute Elo.
- **The champion on Lichess**: the darwin-chess-bot bot keeps playing other bots with the champion of the moment. Every loss is analysed by Stockfish and goes back to the agent as a lesson.
- **The live view**: the game in progress, the agent's thinking, the last verdict and the day's spending, updated in real time.
- **A small budget**: at most 2 dollars a day of language model, spread over the hours. A session costs less than a cent.
