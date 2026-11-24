# Contract

You own this repository. It must build a chess engine that the referee can play against.

## What the referee requires

1. `cargo build --release` produces the binary `target/release/genome`.
2. The binary speaks UCI on stdin/stdout. At minimum: `uci` -> `uciok`, `isready` -> `readyok`,
   `ucinewgame`, `position startpos|fen <fen> [moves ...]`, `go wtime <ms> btime <ms> winc <ms> binc <ms>`
   -> `bestmove <move>`, `quit`.
3. A `perft <depth>` command on the current position prints, for each legal move,
   `<move>: <count>` and then `total: <count>`. The referee uses it to verify your move generator
   on random positions.

## How you are judged

Every candidate passes the gates in order and stops at the first failure:

1. **build**: the release build succeeds.
2. **perft**: counts match the reference on random positions.
3. **smoke**: fast games without illegal moves, crashes or timeouts.
4. **sprt**: a statistical match against the current champion.

An illegal move, a crash or a timeout loses the game. You cannot see or change the referee.

## Resources

- No network. Use the standard library or crates already vendored in this repository.
- Each engine process gets one CPU core during matches.
