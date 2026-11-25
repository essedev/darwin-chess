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

- No network. Use the standard library or the vendored crates: rand 0.9, rayon 1.12,
  bytemuck 1.25. Python 3 with PyTorch (CPU) and numpy is there for training, not for the engine.
- The referee runs `target/release/genome` alone, with no other file: embed everything the
  engine needs (network weights, tables) in the binary, for example with `include_bytes!`.
- Each engine process gets one CPU core during matches.
