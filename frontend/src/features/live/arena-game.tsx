import { useState } from 'react'
import { useI18n } from '@/i18n/context'
import type { LiveGame, Overview } from '@/lib/api'
import { playerName } from './format'
import { GameFrame, Outcome, Player, Score, START } from './game-parts'

type Ready = Extract<Overview, { ready: true }>

/** Ours in a referee game: the candidate on trial, or the champion being rated. */
function oursIn(game: LiveGame): string {
  const engines = [game.white, game.black]
  return engines.find((e) => e === 'candidate') ?? engines.find((e) => e === 'champion' || /^gen-\d+$/.test(e)) ?? game.white
}

/**
 * Games won in the whole match by each side. During a trial: the batches the referee has
 * closed, plus the finished games of the batch still running (not yet in its count). Never
 * shown going down: between a batch closing and the overview catching up, the sum dips.
 */
function useMatchWins(data: Ready, game: LiveGame | null, ours: string, theirs: string) {
  // The highest count seen in this trial: derived state, updated during render (React's
  // pattern for it), so a dip between two sources never reaches the screen.
  const [best, setBest] = useState<{ trial: number | null; ours: number; theirs: number }>({ trial: null, ours: 0, theirs: 0 })
  if (!game) return null
  const progress = data.on_trial?.progress ?? null
  const live = (engine: string) => (game.running ? game.tally[engine]?.wins ?? 0 : 0)
  const trial = progress && ours === 'candidate' ? data.on_trial?.id ?? null : null
  if (trial === null) {
    return { ours: game.tally[ours]?.wins ?? 0, theirs: game.tally[theirs]?.wins ?? 0 }
  }
  const now = { ours: (progress?.wins ?? 0) + live(ours), theirs: (progress?.losses ?? 0) + live(theirs) }
  const kept = best.trial === trial ? best : { trial, ours: 0, theirs: 0 }
  const shown = { trial, ours: Math.max(kept.ours, now.ours), theirs: Math.max(kept.theirs, now.theirs) }
  if (shown.trial !== best.trial || shown.ours !== best.ours || shown.theirs !== best.theirs) setBest(shown)
  return shown
}

/**
 * The referee's game on the board, always from our side: ours below, the board turned when
 * it plays black, so the names stay put while the colours alternate from game to game.
 * Beside each name, the games it has won in the match; once a game ends, its result too.
 */
export function ArenaGame({ data, game }: { data: Ready; game: LiveGame | null }) {
  const i18n = useI18n()
  const { t } = i18n
  const name = (engine: string) => playerName(i18n, engine, (data.on_trial ?? data.current)?.id, data.champion.id)
  const ours = game ? oursIn(game) : ''
  const oursColour = game && game.white === ours ? 'white' : 'black'
  const theirs = game ? (oursColour === 'white' ? game.black : game.white) : ''
  const wins = useMatchWins(data, game, ours, theirs)
  if (!game) {
    return (
      <GameFrame top={<Player colour="black" label={t('arena.waiting')} detail="" />} bottom={<Player colour="white" label="" detail="" />}
                 fen={START} lastMove={null} san={[]} startPly={0} />
    )
  }
  const theirsColour = oursColour === 'white' ? 'black' : 'white'
  const outcome = !game.result ? null
    : game.result === '1/2-1/2' ? 'draw'
    : (game.result === '1-0') === (oursColour === 'white') ? 'win' : 'loss'
  return (
    <GameFrame
      top={<Player colour={theirsColour} label={name(theirs)} detail={t(`colour.${theirsColour}`)}
                   aside={wins && <Score wins={wins.theirs} />} />}
      bottom={
        <Player colour={oursColour} label={name(ours)} detail={t(`colour.${oursColour}`)}
                aside={<span className="flex items-center gap-3">{outcome && <Outcome outcome={outcome} />}{wins && <Score wins={wins.ours} />}</span>} />
      }
      fen={game.fen}
      lastMove={game.last_move}
      san={game.san}
      startPly={game.start_ply}
      orientation={oursColour}
    />
  )
}
