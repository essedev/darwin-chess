import { ArrowLeft, ArrowRight } from 'lucide-react'
import { type ReactNode, useEffect, useMemo } from 'react'
import { BackLink } from '@/components/back-link'
import { ErrorNote, LoadingNote, StateNote, card } from '@/components/page'
import { panel } from '@/components/panel'
import { duration } from '@/features/live/format'
import { useI18n } from '@/i18n/context'
import { isClientError, type SessionDetail, useSession } from '@/lib/api'
import { useNow } from '@/lib/use-now'
import { href } from '@/lib/use-route'
import { cn } from '@/lib/utils'
import { CallRow } from './call-row'
import { mergeEvents } from './model'
import { CursorRow, NoteRow, StatusRow } from './note-rows'
import { SessionEnd } from './session-end'
import { SessionJobs } from './session-jobs'
import { useSessionModel } from './use-session-model'
import { useSessionStream } from './use-session-stream'

/**
 * One agent session as a log (concept D, variant A): a line per tool call in words, the raw
 * call and its answer a click away, thoughts and reasoning in between, the outcome at the end.
 * A running session grows live from the event stream.
 */
export default function SessionPage({ params }: { params: URLSearchParams }) {
  const { t } = useI18n()
  const raw = params.get('id') ?? ''
  const id = /^\d+$/.test(raw) && Number(raw) > 0 ? Number(raw) : null
  const query = useSession(id, 15000)

  useEffect(() => {
    window.scrollTo(0, 0)
  }, [id])

  if (id === null) return <Shell><StateNote title={t('session.missing.title')} text={t('session.missing.text')} className={card} /></Shell>
  if (query.isPending) return <Shell><LoadingNote what={t('what.session')} /></Shell>
  if (query.isError) {
    return (
      <Shell>
        {isClientError(query.error) ? (
          <StateNote title={t('session.missing.title')} text={t('session.missing.text')} className={card} />
        ) : (
          <ErrorNote what={t('what.session')} onRetry={() => void query.refetch()} />
        )}
      </Shell>
    )
  }
  return <Session session={query.data} />
}

function Shell({ children }: { children: ReactNode }) {
  return (
    <main className="grid content-start gap-6 px-4 pt-3 pb-10 sm:px-8 sm:pt-5">
      <div className="-mb-4">
        <BackLink fallback="evoluzione" />
      </div>
      {children}
    </main>
  )
}

function Session({ session: s }: { session: SessionDetail }) {
  const { t } = useI18n()
  const live = s.status === 'running'
  const streamed = useSessionStream(s.id, live)
  const events = useMemo(() => mergeEvents(s.events, streamed, s.id), [s.events, streamed, s.id])
  const model = useSessionModel(events)
  const now = useNow(1000, live)
  return (
    <Shell>
      <Head session={s} calls={model.calls.length} thoughts={model.thoughts} reasonings={model.reasonings} started={model.started} now={now} />
      {model.items.length === 0 ? (
        <StateNote
          art={live ? 'loading' : 'empty'}
          title={live ? t('work.justStarted') : t('session.empty.title')}
          text={live ? t('session.emptyLive') : t('session.empty.text')}
          className={card}
        />
      ) : (
        <section className={cn(panel, 'min-w-0 p-2')}>
          <ol aria-label={t('session.log')} className="grid">
            {model.items.map((item) =>
              item.type === 'call' ? <CallRow key={item.id} call={item} live={live} now={now} />
                : item.type === 'status' ? <StatusRow key={item.id} status={item} sessionId={s.id} base={s.base_generation_id} />
                : <NoteRow key={item.id} note={item} />,
            )}
            {live && <CursorRow now={now} />}
          </ol>
        </section>
      )}
      {s.truncated && <p className="text-[13px] text-muted-foreground">{t('session.truncated', { n: s.events.length })}</p>}
      <SessionEnd session={s} />
      <SessionJobs jobs={s.jobs} />
      <SessionNav session={s} />
    </Shell>
  )
}

function Head(props: { session: SessionDetail; calls: number; thoughts: number; reasonings: number; started: string | null; now: number }) {
  const i18n = useI18n()
  const { t, tn, f, lang } = i18n
  const s = props.session
  const live = s.status === 'running'
  const start = props.started ?? s.created_at
  const title = lang === 'it' ? s.title?.it ?? s.title?.en : s.title?.en ?? s.title?.it
  return (
    <header className="grid gap-1.5">
      <SessionNav session={s} compact />
      <h1 className="flex flex-wrap items-baseline gap-x-3 text-[26px] font-semibold tracking-tight sm:text-[30px]">
        {t('session.title', { id: s.id })}
        {s.kind === 'reflection' && <span className="text-[15px] font-medium text-c-gens">{t('session.reflection')}</span>}
      </h1>
      {title && <p className="text-[17px] font-medium text-balance">{title}</p>}
      <p className="max-w-[72ch] text-[15px] leading-relaxed text-pretty text-muted-foreground">{t('session.intro')}</p>
      <p className="max-w-[72ch] text-[13px] text-muted-foreground">{t('session.how')}</p>
      <p className="mt-1.5 flex flex-wrap gap-x-3.5 gap-y-1.5 text-[13px] text-muted-foreground tabular-nums">
        <span className={cn('inline-flex items-center gap-[7px] font-medium', live ? 'text-live' : '')}>
          {live && <i className="size-[7px] rounded-full bg-current motion-safe:animate-pulse" aria-hidden />}
          {live ? t('session.live') : t('session.over')}
        </span>
        <span>{t('session.startedAt', { time: f.time(start) })}</span>
        {s.base_generation_id !== null && <span>{t('session.base', { gen: s.base_generation_id })}</span>}
        <span>{t('session.actionsOf', { n: f.num(props.calls), max: f.num(s.limits.tool_calls) })}</span>
        <span>{props.thoughts ? tn('count.thoughts', props.thoughts) : t('work.noThoughts')}</span>
        {props.reasonings > 0 && <span>{tn('count.reasonings', props.reasonings)}</span>}
        {live && (
          <span>{t('session.elapsed', { duration: duration(i18n, props.now - Date.parse(start)), max: tn('count.minutes', s.limits.minutes) })}</span>
        )}
        {s.cost_usd > 0 && <span>{t('session.cost', { cost: f.preciseMoney(s.cost_usd) })}</span>}
      </p>
    </header>
  )
}

/** The sessions on either side, by number: every kind, reflections included. */
function SessionNav({ session: s, compact }: { session: SessionDetail; compact?: boolean }) {
  const { t } = useI18n()
  const pill = 'inline-flex h-7 items-center gap-1.5 rounded-full px-3 font-mono text-[12px] font-medium'
  const side = (other: number | null, next: boolean) =>
    other === null ? null : (
      <a
        href={href('sessione', { id: String(other) })}
        aria-label={t(next ? 'session.next' : 'session.previous', { id: other })}
        className={cn(pill, 'cursor-pointer bg-muted text-muted-foreground transition-colors hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/60 focus-visible:outline-none')}
      >
        {!next && <ArrowLeft aria-hidden className="size-3.5" />}#{other}
        {next && <ArrowRight aria-hidden className="size-3.5" />}
      </a>
    )
  if (s.previous === null && s.next === null) return null
  return (
    <nav aria-label={t('session.nav')} className={cn('flex flex-wrap gap-1.5', compact ? 'mb-1' : 'justify-between')}>
      {side(s.previous, false)}
      {side(s.next, true)}
    </nav>
  )
}
