import { useMemo } from 'react'
import { Panel, PanelFooter } from '@/components/panel'
import { clock, duration, plainText } from '@/features/live/format'
import { type I18n, useI18n } from '@/i18n/context'
import { type AgentEvent, useSession } from '@/lib/api'
import { useNow } from '@/lib/use-now'
import { href } from '@/lib/use-route'
import { cn } from '@/lib/utils'
import { TONE } from './describe'
import { type Call, mergeEvents, type SessionModel } from './model'
import { upper, useSessionModel } from './use-session-model'

const TAIL = 8

/**
 * What the agent is doing when there is no game on the board (concept D, variant A): the
 * action in progress in words, how long it has been at it or how long it still waits, and the
 * tail of the session's log, with the way to the whole session.
 */
export function WorkCard(props: { experimentId: number; running: boolean; streamed: AgentEvent[] }) {
  const { experimentId, streamed } = props
  const i18n = useI18n()
  const { t, tn, f, lang } = i18n
  const query = useSession(experimentId, 60000)
  const base = query.data?.events
  const events = useMemo(() => mergeEvents(base ?? [], streamed, experimentId), [base, streamed, experimentId])
  const model = useSessionModel(events)
  const live = query.data ? query.data.status === 'running' : props.running
  const now = useNow(1000, live)
  const start = model.started ?? query.data?.created_at ?? null
  const tail = model.items.filter((i) => i.type !== 'status').slice(-TAIL)
  const ended = query.data?.finished_at ?? model.last
  return (
    <Panel
      hue="live"
      title={t(live ? 'work.label' : 'work.labelOver', { id: experimentId })}
      action={live && start && <span className="font-mono text-[12px] text-muted-foreground tabular-nums">{clock(now - Date.parse(start))}</span>}
    >
      <p className="text-[20px] leading-tight font-semibold tracking-tight text-balance">
        {live ? (model.pending ? upper(model.pending.desc.text) : t('work.choosing'))
          : ended ? t('work.endedAt', { time: f.time(ended) }) : t('session.over')}
      </p>
      {live && <NowDetail i18n={i18n} model={model} now={now} />}
      <ol aria-label={t('work.tail')} className="mt-4 grid gap-0.5 rounded-[10px] bg-muted/70 px-3 py-2.5 font-mono text-[12.5px]">
        {tail.length ? (
          tail.map((item) => (
            <li key={item.id} className="grid grid-cols-[62px_minmax(0,1fr)] gap-2.5 py-[3px]">
              <span className="text-muted-foreground tabular-nums">{f.timeSeconds(item.at)}</span>
              {item.type === 'call' ? (
                <span className={cn('min-w-0 [overflow-wrap:anywhere]', !item.result && live && 'text-live')}>
                  {upper(item.desc.text)}
                  {item.out && <span className={TONE[item.out.tone]}> · {item.out.text}</span>}
                </span>
              ) : (
                <span
                  className={cn('line-clamp-2 min-w-0 font-sans', item.type === 'thought' ? 'text-c-gens' : 'text-muted-foreground')}
                  lang={item.type === 'thought' && lang === 'it' && item.italian ? 'it' : 'en'}
                >
                  {plainText(item.type === 'thought' && lang === 'it' && item.italian ? item.italian : item.text)}
                </span>
              )}
            </li>
          ))
        ) : (
          <li className="text-muted-foreground">{t('work.justStarted')}</li>
        )}
      </ol>
      <PanelFooter>
        <span>
          {tn('count.actions', model.calls.length)} · {model.thoughts ? tn('count.thoughts', model.thoughts) : t('work.noThoughts')}
        </span>
        <a href={href('sessione', { id: String(experimentId) })} className="cursor-pointer font-medium text-live underline-offset-4 hover:underline">
          {t(live ? 'work.follow' : 'work.see')} →
        </a>
      </PanelFooter>
    </Panel>
  )
}

/** When the agent waits on purpose (sleep), the end of the wait; else how long it has been. */
function waitOf(call: Call | null): { from: number; until: number } | null {
  if (!call?.desc.wait) return null
  const from = Date.parse(call.at)
  return { from, until: from + call.desc.wait * 1000 }
}

function NowDetail({ i18n, model, now }: { i18n: I18n; model: SessionModel; now: number }) {
  const { t } = i18n
  const wait = waitOf(model.pending)
  const sub = 'mt-2 text-[12px] text-muted-foreground tabular-nums'
  if (wait) {
    const left = wait.until - now
    const share = Math.max(0, Math.min(1, (now - wait.from) / (wait.until - wait.from)))
    return (
      <>
        <div className="mt-2.5 h-1.5 overflow-hidden rounded-full bg-muted" aria-hidden>
          <i className="block h-1.5 rounded-full bg-live" style={{ width: `${share * 100}%` }} />
        </div>
        <p className={sub}>{left > 0 ? t('work.left', { duration: duration(i18n, left) }) : t('work.timeUp')}</p>
      </>
    )
  }
  if (model.pending) return <p className={sub}>{t('work.since', { duration: duration(i18n, now - Date.parse(model.pending.at)) })}</p>
  if (model.last && model.calls.length) return <p className={sub}>{t('work.lastAnswer', { duration: duration(i18n, now - Date.parse(model.last)) })}</p>
  return <p className={sub}>{t('work.justStarted')}</p>
}
