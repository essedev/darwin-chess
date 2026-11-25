import type { LiveGame, Overview } from '@/lib/api'
import { playerName } from './format'
import { GameFrame, Player, Points, START } from './game-parts'

type Ready = Extract<Overview, { ready: true }>

/** The referee's game on the board: a candidate on trial or a champion being rated. */
export function ArenaGame({ data, game }: { data: Ready; game: LiveGame | null }) {
  const name = (engine: string) => playerName(engine, data.current?.id, data.champion.id)
  const points = (engine: string) => <Points value={game?.tally[engine]?.wins ?? 0} />
  return (
    <GameFrame
      top={
        <Player colour="black" label={game ? name(game.black) : 'In attesa di una partita'}
                detail={game ? 'nero' : ''} aside={game ? points(game.black) : null} />
      }
      bottom={
        <Player colour="white" label={game ? name(game.white) : ''}
                detail={game ? 'bianco' : ''} aside={game ? points(game.white) : null} />
      }
      fen={game?.fen ?? START}
      lastMove={game?.last_move ?? null}
      san={game?.san ?? []}
      startPly={game?.start_ply ?? 0}
    />
  )
}
