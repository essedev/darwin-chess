import { ExternalLink } from 'lucide-react'
import { pickText, useI18n } from '@/i18n/context'
import type { Lichess, LichessGame } from '@/lib/api'
import { cn } from '@/lib/utils'
import { ClampText } from './clamp-text'
import { RESULT_TONE } from './format'

const card = 'rounded-[18px] bg-card p-5 shadow-[inset_0_0_0_1px_var(--border)]'

type Query = { isError: boolean; data: Lichess | undefined }

/**
 * The bot's last finished games on Lichess, newest first, always under the board. Loading and
 * a failed first load are told by the panel above, on the same query: here they show nothing.
 */
export function RecentGames({ query }: { query: Query }) {
  const { t } = useI18n()
  if (!query.data) return null
  const games = query.data.recent
  return (
    <section aria-labelledby="lichess-recent" className={card}>
      <h2 id="lichess-recent" className="mb-2.5 text-[13px] font-normal text-muted-foreground">{t('lichess.recent')}</h2>
      {games.length === 0 ? (
        <p className="text-[13px]">{t('lichess.noneFinished')}</p>
      ) : (
        <ol className="-mx-2.5 grid gap-1">
          {games.map((game) => (
            <Row key={game.lichess_id} game={game} />
          ))}
        </ol>
      )}
      {query.isError && <p className="mt-2 text-[12px] text-muted-foreground">{t('list.stale')}</p>}
    </section>
  )
}

function Row({ game }: { game: LichessGame }) {
  const { t, label, lang, f } = useI18n()
  const tone = RESULT_TONE[game.result ?? ''] ?? 'text-muted-foreground'
  const result = game.result ? label('result', game.result) : game.status
  const commentary = pickText(lang, { it: game.commentary?.it, en: game.commentary?.en })
  const meta = [
    t('lichess.as', { gen: game.generation_id, colour: t(`colour.${game.color}`) }),
    game.time_control,
    game.finished_at ? f.dateTime(game.finished_at) : '',
  ].filter(Boolean)
  return (
    <li className="grid gap-1 rounded-[10px] px-2.5 py-2 hover:bg-muted/50">
      <a
        href={game.url}
        target="_blank"
        rel="noreferrer"
        className="group grid cursor-pointer grid-cols-[64px_minmax(0,1fr)_auto] items-center gap-2.5 rounded-md focus-visible:ring-2 focus-visible:ring-ring/60 focus-visible:outline-none"
      >
        <b className={cn('text-[13px] font-semibold', tone)}>{result}</b>
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
          <span className="block truncate text-[11px] text-muted-foreground">{meta.join(' · ')}</span>
        </span>
        <ExternalLink aria-hidden className="size-4 text-muted-foreground transition-colors group-hover:text-live" />
        <span className="sr-only">{t('lichess.opensOnLichess')}</span>
      </a>
      {commentary && (
        <ClampText text={commentary.text} lang={commentary.lang} badge={commentary.fallback}
                   className="pl-[74px] text-[13px] leading-relaxed text-muted-foreground max-sm:pl-0" />
      )}
    </li>
  )
}
