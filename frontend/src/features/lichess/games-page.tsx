import { ChevronRight, ExternalLink } from 'lucide-react'
import { useState } from 'react'
import { ErrorNote, LoadingNote, PageShell, StateNote } from '@/components/page'
import { PageButton } from '@/components/page-button'
import { panel } from '@/components/panel'
import { MIN_PERFORMANCE_GAMES, RESULT_TONE } from '@/features/live/format'
import { type I18n, pickText, useI18n } from '@/i18n/context'
import { type LichessFilter, type LichessGamesPage, type LichessHistoryGame, useLichessGames } from '@/lib/api'
import { href } from '@/lib/use-route'
import { cn } from '@/lib/utils'
import { Spark } from './eval-chart'
import { MARK, MARK_TONE } from './review'

const PER_PAGE = 20
const RESULTS = [null, 'win', 'draw', 'loss'] as const

/** Every finished Lichess game of the bot, newest first, grouped by day, filtered. */
export default function GamesPage() {
  const { t, f } = useI18n()
  const [filter, setFilter] = useState<LichessFilter>({ generation: null, result: null, rated: false })
  // The cursors of the pages seen so far, as on the list of experiments.
  const [cursors, setCursors] = useState<(number | null)[]>([null])
  const cursor = cursors.at(-1) ?? null
  const page = useLichessGames(filter, cursor, PER_PAGE)
  const data = page.data
  const items = data?.items ?? []
  const change = (next: Partial<LichessFilter>) => {
    setFilter((current) => ({ ...current, ...next }))
    setCursors([null])
  }
  const shown = data ? (filter.result ? data.counts[filter.result] : data.counts.total) : null
  const first = (cursors.length - 1) * PER_PAGE + 1
  const unfiltered = filter.generation === null && filter.result === null && !filter.rated
  return (
    <PageShell title={t('games.title')} intro={t('games.intro')}>
      {data && <Summary page={data} generation={filter.generation} />}
      <div className="flex flex-wrap items-center gap-2.5">
        <label className="sr-only" htmlFor="games-generation">{t('games.generation.label')}</label>
        <select
          id="games-generation"
          value={filter.generation ?? ''}
          onChange={(event) => change({ generation: event.target.value === '' ? null : Number(event.target.value) })}
          className="h-[34px] cursor-pointer rounded-[14px] bg-muted px-3 text-[13px] font-medium text-foreground focus-visible:ring-2 focus-visible:ring-ring/60 focus-visible:outline-none"
        >
          <option value="">{t('games.generation.all')}</option>
          {data?.generations.map((g) => (
            <option key={g.id} value={g.id}>{t('games.generation.one', { gen: g.id, n: f.num(g.games) })}</option>
          ))}
        </select>
        <div role="group" aria-label={t('games.filter.label')} className="inline-flex w-fit max-w-full flex-wrap rounded-[14px] bg-muted p-[3px]">
          {RESULTS.map((result) => {
            const count = data ? data.counts[result ?? 'total'] : null
            return (
              <button
                key={result ?? 'all'}
                type="button"
                aria-pressed={filter.result === result}
                onClick={() => change({ result })}
                className={cn(
                  'inline-flex h-7 cursor-pointer items-center gap-1.5 rounded-[11px] px-3 text-[13px] font-medium transition-colors',
                  filter.result === result ? 'bg-card text-foreground shadow-[0_1px_2px_rgb(0_0_0/0.12)]' : 'text-muted-foreground hover:text-foreground',
                )}
              >
                {t(`games.filter.${result ?? 'all'}`)}
                {count !== null && <span className="font-mono text-[11px] text-muted-foreground tabular-nums">{f.num(count)}</span>}
              </button>
            )
          })}
        </div>
        <button
          type="button"
          aria-pressed={filter.rated}
          onClick={() => change({ rated: !filter.rated })}
          className={cn(
            'inline-flex h-[34px] cursor-pointer items-center gap-2 rounded-[14px] px-3 text-[13px] font-medium transition-colors',
            filter.rated ? 'bg-foreground text-background' : 'bg-muted text-muted-foreground hover:text-foreground',
          )}
        >
          {t('games.rated')}
        </button>
      </div>
      {page.isPending ? (
        <LoadingNote what={t('what.games')} />
      ) : page.isError && items.length === 0 ? (
        <ErrorNote what={t('what.games')} onRetry={() => void page.refetch()} />
      ) : items.length === 0 ? (
        unfiltered ? (
          <StateNote art="empty" title={t('games.none.title')} text={t('games.none.text')} className={cn(panel, 'p-5')} />
        ) : (
          <StateNote title={t('games.noneHere')} className={cn(panel, 'p-5')} />
        )
      ) : (
        <>
          {page.isError && <p className="text-[12px] text-muted-foreground">{t('list.stale')}</p>}
          <div className={cn('grid gap-6 transition-opacity', page.isPlaceholderData && 'opacity-60')}>
            {byDay(items).map(([day, games]) => (
              <section key={day} aria-label={day === '' ? undefined : f.longDate(day)} className="grid gap-2">
                {day && <h2 className="font-mono text-[11px] font-medium tracking-wider text-muted-foreground uppercase">{f.longDate(day)}</h2>}
                <ol className={cn(panel, 'grid divide-y px-2')}>
                  {games.map((game) => <Row key={game.id} game={game} />)}
                </ol>
              </section>
            ))}
          </div>
          <div className="flex flex-wrap items-center justify-between gap-3 text-[13px] text-muted-foreground">
            <span className="tabular-nums">
              {shown !== null && t('experiments.range', { from: f.num(first), to: f.num(first + items.length - 1), of: f.num(shown) })}
            </span>
            <span className="flex gap-1.5">
              <PageButton disabled={cursors.length === 1} onClick={() => setCursors((all) => all.slice(0, -1))}>
                {t('experiments.newer')}
              </PageButton>
              <PageButton
                disabled={!data?.next_before_id || page.isPlaceholderData}
                onClick={() => {
                  const next = data?.next_before_id
                  if (next) setCursors((all) => [...all, next])
                }}
              >
                {t('experiments.older')}
              </PageButton>
            </span>
          </div>
        </>
      )}
      {data?.profile_url && (
        <a href={data.profile_url} target="_blank" rel="noreferrer"
           className="inline-flex w-fit cursor-pointer items-center gap-1.5 text-[13px] font-medium text-live underline-offset-4 hover:underline">
          {t('lichess.onLichess')} <ExternalLink aria-hidden className="size-3.5" />
        </a>
      )}
    </PageShell>
  )
}

/** The games of each day, in the visitor's time zone, in the order they came. */
function byDay(games: LichessHistoryGame[]): [string, LichessHistoryGame[]][] {
  const days = new Map<string, LichessHistoryGame[]>()
  for (const game of games) {
    const day = game.finished_at ? new Date(game.finished_at).toDateString() : ''
    const list = days.get(day) ?? []
    list.push(game)
    days.set(day, list)
  }
  return [...days.entries()].map(([day, list]) => [day === '' ? '' : (list[0]?.finished_at ?? ''), list])
}

/** Wins, draws and losses under the filters, and the performance of the generation shown. */
function Summary({ page, generation }: { page: LichessGamesPage; generation: number | null }) {
  const { t, tn, f } = useI18n()
  const gen = generation ?? page.generations[0]?.id ?? null
  const perf = gen === null ? undefined : page.performance[String(gen)]
  if (page.counts.total === 0) return null
  return (
    <p className="flex flex-wrap gap-x-3.5 gap-y-1 text-[14px] text-muted-foreground tabular-nums">
      <span className="font-medium text-foreground">{tn('count.games', page.counts.total)}</span>
      <span>{t('matches.wdl', { w: f.num(page.counts.win), d: f.num(page.counts.draw), l: f.num(page.counts.loss) })}</span>
      {gen !== null && perf && (
        <span>
          {perf.games >= MIN_PERFORMANCE_GAMES
            ? t('games.performance', { gen, elo: f.num(perf.performance), games: tn('count.ratedGames', perf.games) })
            : t('games.performanceFew', { gen, games: tn('count.ratedGames', perf.games) })}
        </span>
      )}
    </p>
  )
}

function Row({ game }: { game: LichessHistoryGame }) {
  const i18n = useI18n()
  const { t, tn, label, lang, f } = i18n
  const commentary = pickText(lang, { it: game.commentary?.it, en: game.commentary?.en })
  const meta = [
    t('lichess.as', { gen: game.generation_id, colour: t(`colour.${game.color}`) }),
    game.time_control,
    game.finished_at ? f.time(game.finished_at) : '',
    tn('count.fullMoves', Math.ceil(game.plies / 2)),
    game.rated ? '' : t('lichess.unrated'),
  ].filter(Boolean)
  return (
    <li>
      <a
        href={href('partita', { id: game.lichess_id })}
        className="group grid cursor-pointer grid-cols-[52px_minmax(0,1fr)_auto] items-center gap-x-3 gap-y-1 rounded-md px-2 py-3 transition-colors hover:bg-muted/60 focus-visible:ring-2 focus-visible:ring-ring/60 focus-visible:outline-none"
      >
        <b className={cn('text-[13px] font-semibold', RESULT_TONE[game.result ?? ''])}>{game.result ? label('result', game.result) : game.status}</b>
        <span className="grid min-w-0 gap-0.5">
          <span className="flex min-w-0 items-baseline gap-2">
            {game.opponent_title && (
              <span className="flex-none rounded-[5px] bg-muted px-1.5 py-px font-mono text-[10px] font-semibold text-muted-foreground">{game.opponent_title}</span>
            )}
            <b className="min-w-0 truncate text-[14px] font-semibold">{game.opponent}</b>
            {game.opponent_rating !== null && (
              <span className="flex-none font-mono text-[12px] text-muted-foreground">{game.opponent_rating}</span>
            )}
          </span>
          <span className="text-[12px] text-muted-foreground">{meta.join(' · ')}</span>
          {commentary && <span lang={commentary.lang} className="line-clamp-1 text-[13px] text-muted-foreground">{commentary.text}</span>}
        </span>
        <span className="flex items-center gap-3">
          {game.ours && <Mistakes ours={game.ours} i18n={i18n} />}
          {game.curve && <span className="hidden sm:block"><Spark values={game.curve} label={t('games.spark')} /></span>}
          <ChevronRight aria-hidden className="size-4 flex-none text-muted-foreground transition-colors group-hover:text-foreground" />
        </span>
      </a>
    </li>
  )
}

/** The bot's serious mistakes in the game, the worst kind first; nothing when it made none. */
function Mistakes({ ours, i18n }: { ours: NonNullable<LichessHistoryGame['ours']>; i18n: I18n }) {
  const { tn } = i18n
  const shown = (['blunder', 'mistake'] as const).filter((j) => ours[j] > 0)
  if (shown.length === 0) return null
  const spoken = shown.map((j) => tn(j === 'blunder' ? 'count.blunders' : 'count.mistakes', ours[j])).join(', ')
  return (
    <span className="flex gap-2 font-mono text-[12px] tabular-nums" title={spoken}>
      <span className="sr-only">{spoken}</span>
      {shown.map((j) => (
        <span key={j} aria-hidden className={cn('font-semibold', MARK_TONE[j])}>{ours[j]}{MARK[j]}</span>
      ))}
    </span>
  )
}
