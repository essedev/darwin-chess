import { ExternalLink } from 'lucide-react'
import { ClampText } from '@/components/clamp-text'
import { Panel, PanelFooter } from '@/components/panel'
import { pickText, useI18n } from '@/i18n/context'
import type { Lichess, LichessGame } from '@/lib/api'
import { cn } from '@/lib/utils'
import { RESULT_TONE } from './format'
import { RECENT_SHOWN } from './judged-matches'

type Query = { isError: boolean; data: Lichess | undefined }

/**
 * The bot's last three games on Lichess, newest first; every game is on Lichess itself.
 * Loading and a failed first load are told by the board panel, on the same query.
 */
export function RecentGames({ query }: { query: Query }) {
  const { t } = useI18n()
  if (!query.data) return null
  const games = query.data.recent
  const profile = query.data.profile_url
  return (
    <Panel title={t('lichess.recent')}>
      {games.length === 0 ? (
        <p className="text-[13px]">{t('lichess.noneFinished')}</p>
      ) : (
        <ol className="grid divide-y">
          {games.slice(0, RECENT_SHOWN).map((game) => (
            <Row key={game.lichess_id} game={game} />
          ))}
        </ol>
      )}
      {query.isError && <p className="mt-2 text-[12px] text-muted-foreground">{t('list.stale')}</p>}
      {profile && (
        <PanelFooter>
          <span />
          <a href={profile} target="_blank" rel="noreferrer"
             className="inline-flex cursor-pointer items-center gap-1.5 font-medium text-live underline-offset-4 hover:underline">
            {t('lichess.all')} <ExternalLink aria-hidden className="size-3.5" />
          </a>
        </PanelFooter>
      )}
    </Panel>
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
    game.finished_at ? f.time(game.finished_at) : '',
  ].filter(Boolean)
  return (
    <li className="grid gap-1 py-3 first:pt-0 last:pb-0">
      <a href={game.url} target="_blank" rel="noreferrer"
         className="group flex min-w-0 cursor-pointer items-baseline gap-2.5 rounded-md focus-visible:ring-2 focus-visible:ring-ring/60 focus-visible:outline-none">
        <b className={cn('w-11 flex-none text-[13px] font-semibold', tone)}>{result}</b>
        <b className="min-w-0 truncate text-[14px] font-semibold">{game.opponent}</b>
        {game.opponent_rating !== null && (
          <span className="flex-none font-mono text-[12px] text-muted-foreground tabular-nums">{game.opponent_rating}</span>
        )}
        <ExternalLink aria-hidden className="ml-auto size-3.5 flex-none self-center text-muted-foreground transition-colors group-hover:text-live" />
        <span className="sr-only">{t('lichess.opensOnLichess')}</span>
      </a>
      <p className="text-[12px] text-muted-foreground">{meta.join(' · ')}</p>
      {commentary && (
        <ClampText text={commentary.text} lang={commentary.lang} className="text-[13px] leading-normal text-muted-foreground" />
      )}
    </li>
  )
}
