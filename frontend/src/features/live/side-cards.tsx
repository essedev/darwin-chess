import { Panel } from '@/components/panel'
import { useI18n } from '@/i18n/context'
import { type Experiment, type JudgedMatch, type Lichess, type MatchProgress, type Overview, useMatches } from '@/lib/api'
import { cn } from '@/lib/utils'
import { titleText } from './format'
import { JobCard } from './job-card'
import { JudgedMatches } from './judged-matches'
import { RecentGames } from './lichess-recent'
import type { Tab } from './stage'

type Ready = Extract<Overview, { ready: true }>

/** The right column: the question on trial, a long job if any, the spend, the last three results. */
export function SideCards({ data, tab, lichess }: { data: Ready; tab: Tab; lichess: { isError: boolean; data: Lichess | undefined } }) {
  const matches = useMatches()
  const last = matches.data?.[0] ?? null
  return (
    <aside className="order-2 grid min-w-0 grid-cols-[minmax(0,1fr)] content-start gap-3.5 xl:order-none">
      <VerdictPanel trial={data.on_trial ?? null} last={last} />
      <JobCard jobs={data.jobs} />
      <SpendPanel spend={data.spend} />
      {tab === 'arena' ? <JudgedMatches query={matches} /> : <RecentGames query={lichess} />}
    </aside>
  )
}

/**
 * While the referee judges, the question it is answering and where the evidence leans; between
 * trials, the last answer it gave.
 */
function VerdictPanel({ trial, last }: { trial: Experiment | null; last: JudgedMatch | null }) {
  const { t } = useI18n()
  if (!trial) {
    return (
      <Panel title={t('verdict.last')} hue="verdict">
        {last ? <LastVerdict match={last} big /> : <p className="text-[22px] font-semibold tracking-tight">{t('verdict.none')}</p>}
      </Panel>
    )
  }
  const progress = trial.progress
  return (
    <Panel hue="verdict" title={t(`verdict.question.${trial.phase === 'evolution' ? 'champion' : trial.phase === 'first_steps' ? 'random' : 'rules'}`)}>
      {progress?.bounds ? (
        <Evidence progress={progress} bounds={progress.bounds} />
      ) : (
        <>
          <p className="text-[22px] font-semibold tracking-tight">{t('verdict.preparing')}</p>
          <p className="mt-1.5 text-[12px] leading-normal text-muted-foreground">{t('verdict.preparingText')}</p>
        </>
      )}
      {last && (
        <div className="mt-3.5 border-t pt-3">
          <LastVerdict match={last} />
        </div>
      )}
    </Panel>
  )
}

/** The LLR as a bar from "reject" to "promote", and the games behind it. */
function Evidence({ progress, bounds }: { progress: MatchProgress; bounds: [number, number] }) {
  const { t, tn, f } = useI18n()
  const [lower, upper] = bounds
  const share = Math.max(-1, Math.min(1, progress.llr >= 0 ? progress.llr / upper : -progress.llr / lower))
  const lean = progress.llr > 0 ? t('verdict.leanYes') : progress.llr < 0 ? t('verdict.leanNo') : t('verdict.leanNone')
  return (
    <>
      <p className="text-[22px] font-semibold tracking-tight text-[var(--hue)]">{t('verdict.unknown')}</p>
      <div className="relative mt-3.5 h-2 overflow-hidden rounded-full bg-muted" role="img"
           aria-label={t('verdict.llrLabel', { llr: f.num(progress.llr), upper: f.num(upper) })}>
        <span className={cn('absolute top-0 h-2', share >= 0 ? 'rounded-r-full bg-good' : 'rounded-l-full bg-bad')}
              style={{ left: `${share >= 0 ? 50 : 50 + share * 50}%`, width: `${Math.abs(share) * 50}%` }} />
        <span className="absolute top-0 left-[calc(50%-1px)] h-2 w-0.5 bg-muted-foreground/50" />
      </div>
      <div className="mt-1.5 flex justify-between font-mono text-[11px] text-muted-foreground">
        <span>{t('verdict.llrReject')}</span>
        <span>{t('verdict.llrAccept')}</span>
      </div>
      <p className="mt-2 text-[12px] leading-normal text-muted-foreground tabular-nums">
        {tn('count.games', progress.games)} · {t('verdict.wdl', { w: f.num(progress.wins), d: f.num(progress.draws), l: f.num(progress.losses) })} · {lean}
      </p>
    </>
  )
}

/** "#15 Pedoni che avanzano: promosso", small under a trial or as the headline between trials. */
function LastVerdict({ match: m, big = false }: { match: JudgedMatch; big?: boolean }) {
  const { t, lang } = useI18n()
  const title = titleText(lang, m.title, { en: m.hypothesis_en, it: m.hypothesis_it })
  const promoted = m.verdict === 'h1'
  const word = promoted ? t('matches.verdict.h1') : m.verdict === 'h0' ? t('matches.verdict.h0') : t('matches.verdict.continue')
  if (big) {
    return (
      <>
        <p className={cn('text-[22px] font-semibold tracking-tight', promoted ? 'text-good' : 'text-bad')}>{word}</p>
        <p className="mt-1 truncate text-[13px]" lang={title?.lang}>
          <span className="font-mono text-muted-foreground">#{m.experiment_id}</span> {title?.text}
        </p>
      </>
    )
  }
  return (
    <p className="truncate text-[12px] text-muted-foreground">
      {t('verdict.lastShort')}{' '}
      <span className="text-foreground" lang={title?.lang}>#{m.experiment_id} {title?.text}</span>,{' '}
      <span className={cn('font-medium', promoted ? 'text-good' : 'text-bad')}>{word}</span>
    </p>
  )
}

function SpendPanel({ spend }: { spend: Ready['spend'] }) {
  const { t, tn, f } = useI18n()
  const share = Math.min(1, spend.usd / spend.budget)
  const full = spend.usd >= spend.budget
  // Every input token the model read, however it was billed: the cache share is out of this.
  const read = spend.tokens.input + spend.tokens.cached + spend.tokens.cache_write
  return (
    <Panel title={t('spend.title')} hue="spend">
      <p className="flex items-baseline gap-2">
        <b className="font-mono text-[30px] leading-none font-medium tracking-[-0.05em] text-[var(--hue)] tabular-nums">{f.money(spend.usd)}</b>
        <span className="font-mono text-[13px] text-muted-foreground">{t('spend.of', { budget: f.money(spend.budget) })}</span>
      </p>
      <div className="mt-3 h-1.5 rounded-full bg-muted">
        <i className={cn('block h-1.5 rounded-full', full ? 'bg-bad' : 'bg-[var(--hue)]')} style={{ width: `${Math.max(share * 100, 2)}%` }} />
      </div>
      <p className="mt-2.5 text-[12px] text-muted-foreground">
        {full ? t('spend.full') : t('spend.sessions', { sessions: tn('count.sessions', spend.sessions) })}
      </p>
      <dl className="mt-3.5 grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-1.5 border-t pt-3 text-[12px]">
        <dt className="text-muted-foreground">{t('spend.model')}</dt>
        <dd className="min-w-0">
          {modelName(spend.model)}
          <span className="text-muted-foreground"> · {t('spend.effortOf', { effort: effortLabel(t, spend.effort) })}</span>
        </dd>
        <dt className="text-muted-foreground">{t('spend.tokens')}</dt>
        <dd className="min-w-0 font-mono tabular-nums">
          {t('spend.tokensValue', {
            read: f.compact(read),
            cached: read > 0 ? `${Math.round((spend.tokens.cached / read) * 100)}%` : '0%',
            written: f.compact(spend.tokens.output),
          })}
        </dd>
        {spend.sessions > 0 && (
          <>
            <dt className="text-muted-foreground">{t('spend.perSession')}</dt>
            <dd className="font-mono tabular-nums">{f.preciseMoney(spend.usd / spend.sessions)}</dd>
          </>
        )}
      </dl>
    </Panel>
  )
}

/** "claude-haiku-5-5" reads "Claude Haiku 5.5"; an id of another shape is shown as it is. */
function modelName(id: string) {
  const match = /^claude-([a-z]+)-(\d+)-(\d+)$/.exec(id.split('/').pop() ?? id)
  if (!match) return id
  const [, family = '', major, minor] = match
  return `Claude ${family.charAt(0).toUpperCase()}${family.slice(1)} ${major}.${minor}`
}

const EFFORTS = ['off', 'minimal', 'low', 'medium', 'high', 'xhigh'] as const

function effortLabel(t: ReturnType<typeof useI18n>['t'], effort: string) {
  const known = EFFORTS.find((e) => e === effort)
  return known ? t(`effort.${known}`) : effort
}
