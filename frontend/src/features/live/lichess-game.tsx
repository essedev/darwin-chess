import { useI18n } from '@/i18n/context'
import type { Lichess, LichessLive } from '@/lib/api'
import { useNow } from '@/lib/use-now'
import { StateNote } from '@/components/page'
import { panel } from '@/components/panel'
import { cn } from '@/lib/utils'
import { clock } from './format'
import { GameFrame, Player } from './game-parts'

const card = `${panel} p-5`

type Query = { isPending: boolean; data: Lichess | undefined }

/** The Lichess tab's board slot: the bot's game in progress, or why there is none to show. */
export function LichessPanel({ query }: { query: Query }) {
  const { t } = useI18n()
  if (!query.data) {
    return query.isPending
      ? <Message art="loading" title={t('lichess.loading')} />
      : <Message art="error" title={t('lichess.error.title')} text={t('lichess.error.text')} />
  }
  const { live } = query.data
  if (live) return <LiveGame live={live} />
  return <Message art="empty" title={t('lichess.idle.title')} text={t('lichess.idle.text')} />
}

function LiveGame({ live }: { live: LichessLive }) {
  const { t } = useI18n()
  const turn = live.fen.split(' ')[1] === 'b' ? 'black' : 'white'
  // Lichess starts the clocks once both sides have moved.
  const ticking = live.moves.length >= 2
  const now = useNow(1000, ticking)
  const elapsed = ticking ? Math.max(0, now - Date.parse(live.updated_at)) : 0
  const remaining = (colour: 'white' | 'black') =>
    (colour === 'white' ? live.wtime : live.btime) - (colour === turn ? elapsed : 0)
  const player = (colour: 'white' | 'black') => {
    const aside = <Clock ms={remaining(colour)} running={ticking && colour === turn} />
    const side = t(`colour.${colour}`)
    if (colour === live.color)
      return <Player colour={colour} label={`darwin-chess-bot · gen-${live.generation}`} detail={side} aside={aside} />
    const rating = live.opponent.rating === null ? t('lichess.unrated') : String(live.opponent.rating)
    return (
      <Player colour={colour} label={live.opponent.name} badge={live.opponent.title}
              detail={`${side} · ${rating}`} aside={aside} />
    )
  }
  // Our bot below and the board from its side, as Lichess shows a game to its player.
  const theirs = live.color === 'white' ? 'black' : 'white'
  return (
    <GameFrame
      top={player(theirs)}
      bottom={player(live.color)}
      fen={live.fen}
      lastMove={live.last_move}
      san={live.san}
      startPly={live.start_ply}
      orientation={live.color}
    />
  )
}

function Clock({ ms, running }: { ms: number; running: boolean }) {
  return (
    <b className={cn(
      'inline-block rounded-md px-2 py-1 font-mono text-lg leading-none font-medium tabular-nums',
      running ? 'bg-live/15 text-foreground' : 'text-muted-foreground',
      running && ms < 20000 && 'bg-bad/15 text-bad',
    )}>
      {clock(ms)}
    </b>
  )
}

/** The board's place when there is no game to show: the same states as the rest of the site. */
function Message({ title, text, art }: { title: string; text?: string; art: 'loading' | 'error' | 'empty' }) {
  return (
    <section className={card}>
      <StateNote big art={art} tone={art === 'error' ? 'bad' : 'muted'} title={title} text={text} />
    </section>
  )
}
