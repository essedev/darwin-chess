import { useI18n } from '@/i18n/context'
import type { Lichess, LichessLive } from '@/lib/api'
import { useNow } from '@/lib/use-now'
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
      ? <Message title={t('lichess.loading')} />
      : <Message title={t('lichess.error.title')} text={t('lichess.error.text')} />
  }
  const { live } = query.data
  if (live) return <LiveGame live={live} />
  return <Message title={t('lichess.idle.title')} text={t('lichess.idle.text')} />
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
  return (
    <GameFrame
      top={player('black')}
      bottom={player('white')}
      fen={live.fen}
      lastMove={live.last_move}
      san={live.san}
      startPly={live.start_ply}
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

function Message({ title, text }: { title: string; text?: string }) {
  return (
    <section className={card}>
      <p className="text-[22px] font-semibold tracking-tight">{title}</p>
      {text && <p className="mt-1.5 text-[13px] text-muted-foreground">{text}</p>}
    </section>
  )
}
