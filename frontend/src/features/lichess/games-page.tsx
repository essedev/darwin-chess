import { ChevronRight, ExternalLink, Search, SlidersHorizontal, X } from 'lucide-react'
import { type ReactNode, useEffect, useState } from 'react'
import { FilterSelect } from '@/components/filter-select'
import { ErrorNote, LoadingNote, PageShell, StateNote } from '@/components/page'
import { PageButton } from '@/components/page-button'
import { panel } from '@/components/panel'
import { MIN_PERFORMANCE_GAMES, RESULT_TONE } from '@/features/live/format'
import { type I18n, pickText, useI18n } from '@/i18n/context'
import { type LichessFilter, type LichessGamesPage, type LichessHistoryGame, type Speed, useLichessGames } from '@/lib/api'
import { href } from '@/lib/use-route'
import { cn } from '@/lib/utils'
import { Spark } from './eval-chart'
import { MARK, MARK_TONE } from './review'

const PER_PAGE = 20
const RESULTS = [null, 'win', 'draw', 'loss'] as const
const OPPONENTS = [null, 'bot', 'human'] as const
const SPEEDS: readonly Speed[] = ['ultrabullet', 'bullet', 'blitz', 'rapid', 'classical', 'correspondence']
const SEARCH_DELAY_MS = 300

/**
 * The filters and the pages seen so far live in the address (`#/partite?gen=17&q=maia`):
 * back from a game, the list is where it was, and a filtered list can be shared.
 */
function readFilter(params: URLSearchParams): { filter: LichessFilter; cursors: (number | null)[] } {
  const gen = params.get('gen')
  const result = params.get('result')
  const opponent = params.get('opp')
  const speed = params.get('speed')
  const pages = (params.get('pages') ?? '').split(',').map(Number).filter((n) => Number.isInteger(n) && n > 0)
  return {
    filter: {
      generation: gen !== null && /^\d+$/.test(gen) ? Number(gen) : null,
      result: result === 'win' || result === 'draw' || result === 'loss' ? result : null,
      rated: params.get('rated') === '1',
      q: (params.get('q') ?? '').slice(0, 64),
      opponent: opponent === 'bot' || opponent === 'human' ? opponent : null,
      speed: SPEEDS.find((s) => s === speed) ?? null,
    },
    cursors: [null, ...pages],
  }
}

function writeFilter(filter: LichessFilter, cursors: (number | null)[]) {
  const target = href('partite', {
    gen: filter.generation === null ? null : String(filter.generation),
    result: filter.result,
    rated: filter.rated ? '1' : null,
    q: filter.q.trim() || null,
    opp: filter.opponent,
    speed: filter.speed,
    pages: cursors.filter((c) => c !== null).join(',') || null,
  })
  // Replaced, not pushed: the back button leaves the list instead of undoing a filter.
  if (window.location.hash !== target) window.location.replace(target)
}

/** Every finished Lichess game of the bot, newest first, grouped by day, filtered. */
export default function GamesPage({ params }: { params: URLSearchParams }) {
  const { t, f } = useI18n()
  const { filter, cursors } = readFilter(params)
  const cursor = cursors.at(-1) ?? null
  const page = useLichessGames(filter, cursor, PER_PAGE)
  const data = page.data
  const items = data?.items ?? []
  const [open, setOpen] = useState(false)
  const change = (next: Partial<LichessFilter>) => writeFilter({ ...filter, ...next }, [null])
  const shown = data ? (filter.result ? data.counts[filter.result] : data.counts.total) : null
  const first = (cursors.length - 1) * PER_PAGE + 1
  const active = [filter.generation !== null, filter.result !== null, filter.rated, filter.opponent !== null, filter.speed !== null]
    .filter(Boolean).length
  const unfiltered = active === 0 && !filter.q.trim()

  const generations = [
    { value: 'all', label: t('games.generation.all') },
    ...(data?.generations ?? []).map((g) => ({ value: String(g.id), label: `gen-${g.id}`, count: f.num(g.games) })),
  ]
  // The generation in the address stays choosable while the list loads or if it has no games.
  if (filter.generation !== null && !generations.some((g) => g.value === String(filter.generation))) {
    generations.push({ value: String(filter.generation), label: `gen-${filter.generation}` })
  }
  const speeds = [
    { value: 'all', label: t('games.speed.all') },
    ...(data?.speeds ?? []).map((s) => ({ value: s.id, label: t(`speed.${s.id}`), count: f.num(s.games) })),
  ]
  if (filter.speed && !speeds.some((s) => s.value === filter.speed)) {
    speeds.push({ value: filter.speed, label: t(`speed.${filter.speed}`) })
  }

  return (
    <PageShell title={t('games.title')} intro={t('games.intro')}>
      {data && <Summary page={data} generation={filter.generation} />}
      <div className="grid gap-2.5">
        <div className="flex gap-2.5">
          <SearchBox value={filter.q} onChange={(q) => change({ q })} />
          <button
            type="button"
            aria-expanded={open}
            aria-controls="games-filters"
            onClick={() => setOpen((value) => !value)}
            className="inline-flex h-[34px] flex-none cursor-pointer items-center gap-2 rounded-[14px] bg-muted px-3 text-[13px] font-medium text-foreground sm:hidden"
          >
            <SlidersHorizontal aria-hidden className="size-3.5" />
            {t('games.filters')}
            {active > 0 && <span className="font-mono text-[11px] text-muted-foreground tabular-nums">{active}</span>}
          </button>
        </div>
        <div id="games-filters" className={cn('flex-wrap items-center gap-2.5', open ? 'flex' : 'hidden sm:flex')}>
          <FilterSelect
            label={t('games.generation.label')}
            value={filter.generation === null ? 'all' : String(filter.generation)}
            options={generations}
            onChange={(value) => change({ generation: value === 'all' ? null : Number(value) })}
          />
          <Segmented label={t('games.filter.label')}>
            {RESULTS.map((result) => (
              <SegmentButton key={result ?? 'all'} pressed={filter.result === result} onClick={() => change({ result })}
                             count={data ? f.num(data.counts[result ?? 'total']) : null}>
                {t(`games.filter.${result ?? 'all'}`)}
              </SegmentButton>
            ))}
          </Segmented>
          <Segmented label={t('games.opponent.label')}>
            {OPPONENTS.map((opponent) => (
              <SegmentButton key={opponent ?? 'all'} pressed={filter.opponent === opponent} onClick={() => change({ opponent })}>
                {t(`games.opponent.${opponent ?? 'all'}`)}
              </SegmentButton>
            ))}
          </Segmented>
          <FilterSelect
            label={t('games.speed.label')}
            value={filter.speed ?? 'all'}
            options={speeds}
            onChange={(value) => change({ speed: SPEEDS.find((s) => s === value) ?? null })}
          />
          <button
            type="button"
            aria-pressed={filter.rated}
            onClick={() => change({ rated: !filter.rated })}
            className={cn(
              'inline-flex h-[34px] cursor-pointer items-center gap-2 rounded-[14px] px-3 text-[13px] font-medium transition-colors focus-visible:ring-2 focus-visible:ring-ring/60 focus-visible:outline-none',
              filter.rated ? 'bg-foreground text-background' : 'bg-muted text-muted-foreground hover:text-foreground',
            )}
          >
            {t('games.rated')}
          </button>
        </div>
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
              <PageButton disabled={cursors.length === 1} onClick={() => writeFilter(filter, cursors.slice(0, -1))}>
                {t('experiments.newer')}
              </PageButton>
              <PageButton
                disabled={!data?.next_before_id || page.isPlaceholderData}
                onClick={() => {
                  const next = data?.next_before_id
                  if (next) writeFilter(filter, [...cursors, next])
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

/** The opponent's name, sent a moment after the typing stops; the address keeps it. */
function SearchBox({ value, onChange }: { value: string; onChange: (q: string) => void }) {
  const { t } = useI18n()
  const [text, setText] = useState(value)
  useEffect(() => {
    if (text.trim() === value.trim()) return
    const timer = window.setTimeout(() => onChange(text.trim()), SEARCH_DELAY_MS)
    return () => window.clearTimeout(timer)
  }, [text, value, onChange])
  return (
    <div className="relative min-w-0 flex-1 sm:max-w-[400px]">
      <Search aria-hidden className="pointer-events-none absolute top-1/2 left-3 size-3.5 -translate-y-1/2 text-muted-foreground" />
      <input
        type="search"
        value={text}
        maxLength={64}
        onChange={(event) => setText(event.target.value)}
        placeholder={t('games.search.placeholder')}
        aria-label={t('games.search.label')}
        className="h-[34px] w-full rounded-[14px] bg-muted pr-9 pl-8 text-[13px] text-foreground placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring/60 focus-visible:outline-none [&::-webkit-search-cancel-button]:hidden"
      />
      {text && (
        <button
          type="button"
          aria-label={t('games.search.clear')}
          onClick={() => {
            setText('')
            onChange('')
          }}
          className="absolute top-1/2 right-1 inline-flex size-[30px] -translate-y-1/2 cursor-pointer items-center justify-center rounded-[10px] text-muted-foreground hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/60 focus-visible:outline-none"
        >
          <X aria-hidden className="size-3.5" />
        </button>
      )}
    </div>
  )
}

function Segmented({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div role="group" aria-label={label} className="inline-flex w-fit max-w-full flex-wrap rounded-[14px] bg-muted p-[3px]">
      {children}
    </div>
  )
}

function SegmentButton(props: { pressed: boolean; onClick: () => void; count?: string | null; children: ReactNode }) {
  return (
    <button
      type="button"
      aria-pressed={props.pressed}
      onClick={props.onClick}
      className={cn(
        'inline-flex h-7 cursor-pointer items-center gap-1.5 rounded-[11px] px-3 text-[13px] font-medium transition-colors focus-visible:ring-2 focus-visible:ring-ring/60 focus-visible:outline-none',
        props.pressed ? 'bg-card text-foreground shadow-[0_1px_2px_rgb(0_0_0/0.12)]' : 'text-muted-foreground hover:text-foreground',
      )}
    >
      {props.children}
      {props.count != null && <span className="font-mono text-[11px] text-muted-foreground tabular-nums">{props.count}</span>}
    </button>
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
    `${t(`speed.${game.speed}`)} ${game.time_control}`,
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
