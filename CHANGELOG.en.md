# Changelog

What is new in the lab, most recent first.

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
