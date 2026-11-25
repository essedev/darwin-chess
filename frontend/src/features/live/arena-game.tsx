import { useI18n } from '@/i18n/context'
import type { LiveGame, Overview } from '@/lib/api'
import { playerName } from './format'
import { GameFrame, Outcome, Player, START } from './game-parts'

type Ready = Extract<Overview, { ready: true }>

/** Ours in a referee game: the candidate on trial, or the champion being rated. */
function oursIn(game: LiveGame): string {
  const engines = [game.white, game.black]
  return engines.find((e) => e === 'candidate') ?? engines.find((e) => e === 'champion' || /^gen-\d+$/.test(e)) ?? game.white
}

/**
 * The referee's game on the board, always from our side: ours below, the board turned when
 * it plays black, so the names stay put while the colours alternate from game to game.
 * The match score is in the verdict panel; here, once the game ends, its result.
 */
export function ArenaGame({ data, game }: { data: Ready; game: LiveGame | null }) {
  const i18n = useI18n()
  const { t } = i18n
  const name = (engine: string) => playerName(i18n, engine, (data.on_trial ?? data.current)?.id, data.champion.id)
  if (!game) {
    return (
      <GameFrame top={<Player colour="black" label={t('arena.waiting')} detail="" />} bottom={<Player colour="white" label="" detail="" />}
                 fen={START} lastMove={null} san={[]} startPly={0} />
    )
  }
  const ours = oursIn(game)
  const oursColour = game.white === ours ? 'white' : 'black'
  const theirs = oursColour === 'white' ? game.black : game.white
  const theirsColour = oursColour === 'white' ? 'black' : 'white'
  const outcome = !game.result ? null
    : game.result === '1/2-1/2' ? 'draw'
    : (game.result === '1-0') === (oursColour === 'white') ? 'win' : 'loss'
  return (
    <GameFrame
      top={<Player colour={theirsColour} label={name(theirs)} detail={t(`colour.${theirsColour}`)} />}
      bottom={
        <Player colour={oursColour} label={name(ours)} detail={t(`colour.${oursColour}`)}
                aside={outcome ? <Outcome outcome={outcome} /> : null} />
      }
      fen={game.fen}
      lastMove={game.last_move}
      san={game.san}
      startPly={game.start_ply}
      orientation={oursColour}
    />
  )
}
