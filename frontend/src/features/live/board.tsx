import { Chessboard } from 'react-chessboard'

const PIECES = ['wK', 'wQ', 'wR', 'wB', 'wN', 'wP', 'bK', 'bQ', 'bR', 'bB', 'bN', 'bP'] as const

// cburnett set, served from public/pieces/cburnett (GPLv2+, see LICENSE.txt there).
const pieces = Object.fromEntries(
  PIECES.map((code) => [
    code,
    () => <img src={`/pieces/cburnett/${code}.svg`} alt="" draggable={false} className="size-full" />,
  ]),
)

export function Board({ fen, lastMove }: { fen: string; lastMove: string | null }) {
  const highlight = { background: 'rgb(242 163 58 / 0.38)' }
  const squareStyles = lastMove ? { [lastMove.slice(0, 2)]: highlight, [lastMove.slice(2, 4)]: highlight } : {}
  return (
    <div className="overflow-hidden rounded-[10px] shadow-[0_0_0_1px_var(--border),0_12px_32px_-12px_rgb(0_0_0/0.35)]">
      <Chessboard
        options={{
          id: 'live',
          position: fen,
          pieces,
          allowDragging: false,
          showNotation: false,
          animationDurationInMs: 150,
          squareStyles,
          lightSquareStyle: { backgroundColor: 'var(--sq-light)' },
          darkSquareStyle: { backgroundColor: 'var(--sq-dark)' },
        }}
      />
    </div>
  )
}
