import { ExternalLink } from 'lucide-react'
import type { LichessGame } from '@/lib/api'
import { RESULTS } from './format'

const card = 'rounded-[18px] bg-card p-5 shadow-[inset_0_0_0_1px_var(--border)]'

/** The bot's last finished games on Lichess, newest first; each opens the game there. */
export function RecentGames({ games }: { games: LichessGame[] }) {
  return (
    <section className={card}>
      <p className="mb-2.5 text-[13px] text-muted-foreground">Ultime partite su Lichess</p>
      {games.length === 0 ? (
        <p className="text-[13px]">Ancora nessuna partita conclusa.</p>
      ) : (
        <ol className="-mx-2.5 grid gap-0.5">
          {games.map((game) => (
            <li key={game.lichess_id}>
              <Row game={game} />
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}

function Row({ game }: { game: LichessGame }) {
  const result = RESULTS[game.result ?? ''] ?? { label: game.status, tone: 'text-muted-foreground' }
  const side = game.color === 'white' ? 'bianco' : 'nero'
  return (
    <a href={game.url} target="_blank" rel="noreferrer"
       className="group grid cursor-pointer grid-cols-[64px_minmax(0,1fr)_auto] items-center gap-2.5 rounded-[10px] px-2.5 py-2 hover:bg-muted">
      <b className={`text-[13px] font-semibold ${result.tone}`}>{result.label}</b>
      <span className="min-w-0">
        <span className="flex items-center gap-1.5">
          {game.opponent_title && (
            <span className="flex-none rounded-[5px] bg-live/15 px-1.5 py-px font-mono text-[10px] font-semibold text-live">
              {game.opponent_title}
            </span>
          )}
          <b className="truncate text-[13px] font-medium">{game.opponent}</b>
          {game.opponent_rating !== null && (
            <span className="font-mono text-[11px] text-muted-foreground tabular-nums">{game.opponent_rating}</span>
          )}
        </span>
        <span className="block truncate text-[11px] text-muted-foreground">
          gen-{game.generation_id} col {side} · {game.time_control} · {when(game.finished_at)}
        </span>
      </span>
      <ExternalLink className="size-4 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100" aria-hidden />
    </a>
  )
}

function when(iso: string | null) {
  if (!iso) return ''
  return new Date(iso).toLocaleString('it-IT', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
}
