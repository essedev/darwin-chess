import { Panel } from '@/components/panel'
import { useI18n } from '@/i18n/context'
import { useMemo } from 'react'
import { upper, useSessionModel } from '@/features/session/use-session-model'
import type { AgentEvent, LichessPerformance, Overview } from '@/lib/api'
import { href } from '@/lib/use-route'
import { cn } from '@/lib/utils'
import { EloChart } from './elo-chart'
import { type EloPoint, MIN_PERFORMANCE_GAMES, overlap, titleText } from './format'

type Ready = Extract<Overview, { ready: true }>

const SHOWN = 5

/** The left column: how strong the champion is, then the latest generations. */
export function History({ data, events, lichess }: { data: Ready; events: AgentEvent[]; lichess: LichessPerformance | undefined }) {
  return (
    <aside className="order-3 grid min-w-0 content-start gap-3.5 lg:col-span-full lg:grid-cols-2 xl:order-none xl:col-span-1 xl:grid-cols-1">
      <Strength data={data} lichess={lichess} />
      <Generations data={data} events={events} />
    </aside>
  )
}

/**
 * The absolute Elo with its margin is the headline: the gain over the previous champion says
 * only that the new one beats the old, and the two can disagree. The chart shows every rated
 * generation with its error bar, so a "drop" inside the margins reads as what it is.
 */
function Strength({ data, lichess }: { data: Ready; lichess: LichessPerformance | undefined }) {
  const { t, tn, f } = useI18n()
  const rated: EloPoint[] = data.generations
    .filter((g) => g.elo_absolute !== null && g.elo_absolute_error != null)
    .map((g) => ({ id: g.id, elo: g.elo_absolute ?? 0, error: g.elo_absolute_error ?? 0 }))
  const champion = data.generations.find((g) => g.id === data.champion.id)
  const own = champion && champion.elo_absolute !== null ? champion : null
  const shared = overlap(rated)
  return (
    <Panel title={t('elo.title')} help={t('elo.help')} hue="strength">
      {own ? (
        <>
          <p className="flex items-baseline gap-2">
            <b className="font-mono text-[44px] leading-none font-medium tracking-[-0.06em] text-[var(--hue)] tabular-nums">
              {f.num(Math.round(own.elo_absolute ?? 0))}
            </b>
            {own.elo_absolute_error != null && (
              <span className="font-mono text-[16px] font-medium text-muted-foreground">± {f.num(Math.round(own.elo_absolute_error))}</span>
            )}
            <span className="font-mono text-[12px] font-medium text-muted-foreground">Elo</span>
          </p>
          <p className="mt-1.5 text-[12px] text-muted-foreground">{t('elo.against', { gen: own.id })}</p>
        </>
      ) : (
        <p className="text-[20px] font-semibold tracking-tight">{t(data.champion.id === 0 ? 'elo.noChampion' : 'elo.notRated')}</p>
      )}
      {rated.length > 0 && (
        <div className="mt-3">
          <EloChart points={rated.slice(-6)} height={104} />
        </div>
      )}
      {rated.length > 1 && (
        <p className="mt-2 text-[12px] leading-normal text-muted-foreground">
          {shared ? t('elo.sameMargin', { gens: rated.slice(-6).map((p) => `gen-${p.id}`).join(', ') }) : t('elo.apart')}
        </p>
      )}
      {lichess && (
        <p className="mt-3.5 border-t pt-3 text-[12px] text-muted-foreground">
          {lichess.games >= MIN_PERFORMANCE_GAMES
            ? t('elo.lichess', { performance: f.num(lichess.performance), games: tn('count.games', lichess.games) })
            : t('elo.lichessFew', { games: tn('count.games', lichess.games) })}
        </p>
      )}
    </Panel>
  )
}

/** The candidate racing now, then the last few champions with their title and rating. */
function Generations({ data, events }: { data: Ready; events: AgentEvent[] }) {
  const { t, lang, f } = useI18n()
  const promoted = data.generations.filter((g) => g.id >= 1).reverse().slice(0, SHOWN)
  const current = data.on_trial ?? (data.current && ['running', 'judging'].includes(data.current.status) ? data.current : null)
  const currentTitle =
    current && titleText(lang, current.title, { en: current.hypothesis, it: current.hypothesis_it })
  return (
    <Panel
      title={t('generations.panel')}
      hue="gens"
      action={
        <a href={href('evoluzione')} className="cursor-pointer text-[12px] font-medium text-[var(--hue)] underline-offset-4 hover:underline">
          {t('generations.all', { n: data.experiments.total })}
        </a>
      }
    >
      <ol className="-mx-2.5 grid gap-0.5">
        {current && current.status === 'running' && <RunningRow id={current.id} events={events} />}
        {current && current.status !== 'running' && (
          <Row tag={`#${current.id}`} now title={currentTitle?.text ?? t('history.working')} lang={currentTitle?.lang}
               subtitle={current.progress ? t('generations.racing', { gen: data.champion.id }) : t('generations.queued')} />
        )}
        {promoted.map((g) => {
          const title = titleText(lang, g.title, { en: g.hypothesis, it: g.hypothesis_it })
          return (
            <Row
              key={g.id}
              tag={`gen-${g.id}`}
              title={title?.text ?? ''}
              lang={title?.lang}
              subtitle={g.tried <= 1 ? t('generations.firstTry') : t('generations.afterTries', { n: g.tried })}
              value={g.elo_absolute === null ? null : f.num(Math.round(g.elo_absolute))}
              error={g.elo_absolute_error == null ? null : `± ${f.num(Math.round(g.elo_absolute_error))}`}
            />
          )
        })}
        {promoted.length === 0 && !current && <li className="px-2.5 text-[13px] text-muted-foreground">{t('history.noChampion')}</li>}
      </ol>
    </Panel>
  )
}

/** The session at work: what it is doing now, in words, and the way to its page. */
function RunningRow({ id, events }: { id: number; events: AgentEvent[] }) {
  const { t } = useI18n()
  const mine = useMemo(() => events.filter((e) => e.experiment_id === id), [events, id])
  const model = useSessionModel(mine)
  const call = model.pending ?? model.calls[model.calls.length - 1] ?? null
  return (
    <Row tag={`#${id}`} now title={t('history.working')} subtitle={call ? upper(call.desc.text) : t('work.choosing')}
         href={href('sessione', { id: String(id) })} />
  )
}

function Row(props: {
  tag: string
  title: string
  subtitle: string
  lang?: string
  value?: string | null
  error?: string | null
  now?: boolean
  href?: string
}) {
  const grid = 'grid grid-cols-[50px_minmax(0,1fr)_auto] items-center gap-2.5 rounded-[10px] px-2.5 py-[9px]'
  const cells = <RowCells {...props} />
  return (
    <li className={cn(!props.href && grid, props.now && 'bg-live/10', props.href && 'rounded-[10px]')}>
      {props.href ? (
        <a href={props.href} className={cn(grid, 'cursor-pointer transition-colors hover:bg-live/15 focus-visible:ring-2 focus-visible:ring-ring/60 focus-visible:outline-none')}>
          {cells}
        </a>
      ) : (
        cells
      )}
    </li>
  )
}

function RowCells(props: Parameters<typeof Row>[0]) {
  return (
    <>
      <span className={cn('font-mono text-xs font-medium text-muted-foreground', props.now && 'text-live')}>{props.tag}</span>
      <span className="min-w-0">
        <b className="block truncate text-[13.5px] font-medium" title={props.title} lang={props.lang}>{props.title}</b>
        <span className="block truncate text-[11.5px] text-muted-foreground">{props.subtitle}</span>
      </span>
      <span className="text-right font-mono text-[13px] font-medium text-c-strength tabular-nums">
        {props.value ?? (props.now ? '' : <span className="text-muted-foreground">–</span>)}
        {props.error && <small className="block text-[10.5px] font-normal text-muted-foreground">{props.error}</small>}
      </span>
    </>
  )
}
