import { useI18n } from '@/i18n/context'
import type { LiveGame, Overview } from '@/lib/api'
import { playerName } from './format'
import { GameFrame, Player, Points, START } from './game-parts'

type Ready = Extract<Overview, { ready: true }>

/** The referee's game on the board: a candidate on trial or a champion being rated. */
export function ArenaGame({ data, game }: { data: Ready; game: LiveGame | null }) {
  const i18n = useI18n()
  const { t } = i18n
  const name = (engine: string) => playerName(i18n, engine, (data.on_trial ?? data.current)?.id, data.champion.id)
  // During a trial the whole match counts (finished batches, from the referee); otherwise
  // the games of the match on the board.
  const progress = data.on_trial?.progress ?? null
  const won = (engine: string) => {
    if (progress && engine === 'candidate') return progress.wins
    if (progress && engine === 'champion') return progress.losses
    return game?.tally[engine]?.wins ?? 0
  }
  const points = (engine: string) => <Points value={won(engine)} />
  return (
    <GameFrame
      top={
        <Player colour="black" label={game ? name(game.black) : t('arena.waiting')}
                detail={game ? t('colour.black') : ''} aside={game ? points(game.black) : null} />
      }
      bottom={
        <Player colour="white" label={game ? name(game.white) : ''}
                detail={game ? t('colour.white') : ''} aside={game ? points(game.white) : null} />
      }
      fen={game?.fen ?? START}
      lastMove={game?.last_move ?? null}
      san={game?.san ?? []}
      startPly={game?.start_ply ?? 0}
    />
  )
}
