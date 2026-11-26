import { useMemo } from 'react'
import { useI18n } from '@/i18n/context'
import { useOverview } from '@/lib/api'
import { href } from '@/lib/use-route'
import { upper, useSessionModel } from './use-session-model'

/**
 * "At work right now: builds · session #38", while a session runs; nothing otherwise. The
 * Mind page holds what the agent knows, the session what it does: this line links the two.
 */
export function WorkingNow() {
  const { t } = useI18n()
  const overview = useOverview()
  const data = overview.data?.ready ? overview.data : null
  const running = data?.current?.status === 'running' ? data.current : null
  const events = useMemo(() => (running && data ? data.events.filter((e) => e.experiment_id === running.id) : []), [running, data])
  const model = useSessionModel(events)
  if (!running) return null
  const call = model.pending ?? model.calls[model.calls.length - 1] ?? null
  return (
    <p className="-mt-2 flex flex-wrap items-baseline gap-x-2 gap-y-1 rounded-[10px] bg-live/8 px-3.5 py-2.5 text-[14px]">
      <span className="inline-flex items-center gap-2 font-medium text-live">
        <i className="size-[7px] rounded-full bg-current motion-safe:animate-pulse" aria-hidden />
        {t('mind.working')}
      </span>
      <span>{call ? upper(call.desc.text) : t('work.choosing')}</span>
      <a href={href('sessione', { id: String(running.id) })} className="cursor-pointer font-medium text-live underline-offset-4 hover:underline">
        {t('work.session', { id: running.id })} →
      </a>
    </p>
  )
}
