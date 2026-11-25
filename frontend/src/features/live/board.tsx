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
    // A tray around the board: 8px of the panel surface, radii concentric (8 + 8 = 16).
    <div className="rounded-[16px] bg-card p-2 shadow-[var(--panel-shadow)]">
      <div className="overflow-hidden rounded-[8px]">
      <Chessboard
        options={{
          id: 'live',
          position: fen,
          pieces,
          allowDragging: false,
          showNotation: true,
          lightSquareNotationStyle: { color: 'var(--sq-dark)' },
          darkSquareNotationStyle: { color: 'var(--sq-light)' },
          alphaNotationStyle: { fontSize: '10px', fontWeight: 600, position: 'absolute', bottom: 2, right: 4, userSelect: 'none' },
          numericNotationStyle: { fontSize: '10px', fontWeight: 600, position: 'absolute', top: 3, left: 4, userSelect: 'none' },
          animationDurationInMs: 150,
          squareStyles,
          lightSquareStyle: { backgroundColor: 'var(--sq-light)' },
          darkSquareStyle: { backgroundColor: 'var(--sq-dark)' },
        }}
      />
      </div>
    </div>
  )
}
