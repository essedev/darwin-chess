import type { Lichess, LichessLive } from '@/lib/api'
import { cn } from '@/lib/utils'
import { useNow } from '@/lib/use-now'
import { clock } from './format'
import { GameFrame, Player } from './game-parts'
import { RecentGames } from './lichess-recent'

const card = 'rounded-[18px] bg-card p-5 shadow-[inset_0_0_0_1px_var(--border)]'

type Query = { isPending: boolean; isError: boolean; data: Lichess | undefined }

/** The Lichess tab: the bot's game in progress, or the games it has finished. */
export function LichessPanel({ query }: { query: Query }) {
  if (query.isPending) return <Message title="Carico le partite su Lichess…" />
  if (query.isError || !query.data)
    return <Message title="Non riesco a leggere le partite su Lichess" text="Riprovo da solo tra poco." />
  const { live, recent } = query.data
  if (live) return <LiveGame live={live} />
  return (
    <div className="grid w-full gap-3.5">
      <Message title="Nessuna partita su Lichess in corso" text="Quando il bot gioca, la partita compare qui in diretta." />
      <RecentGames games={recent} />
    </div>
  )
}

function LiveGame({ live }: { live: LichessLive }) {
  const turn = live.fen.split(' ')[1] === 'b' ? 'black' : 'white'
  // Lichess starts the clocks once both sides have moved.
  const ticking = live.moves.length >= 2
  const now = useNow(1000, ticking)
  const elapsed = ticking ? Math.max(0, now - Date.parse(live.updated_at)) : 0
  const remaining = (colour: 'white' | 'black') =>
    (colour === 'white' ? live.wtime : live.btime) - (colour === turn ? elapsed : 0)
  const player = (colour: 'white' | 'black') => {
    const aside = <Clock ms={remaining(colour)} running={ticking && colour === turn} />
    const side = colour === 'white' ? 'bianco' : 'nero'
    if (colour === live.color)
      return <Player colour={colour} label={`darwin-chess-bot · gen-${live.generation}`} detail={side} aside={aside} />
    const rating = live.opponent.rating === null ? 'senza punteggio' : String(live.opponent.rating)
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
