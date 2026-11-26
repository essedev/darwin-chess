import { useMemo } from 'react'
import { useI18n } from '@/i18n/context'
import type { AgentEvent } from '@/lib/api'
import { href } from '@/lib/use-route'
import { upper, useSessionModel } from './use-session-model'

/**
 * One line under the board while a session runs: what the agent is doing, in words, and the
 * way to its session. It takes the place of the last thought, which the session page keeps.
 */
export function AgentLine({ experimentId, events }: { experimentId: number; events: AgentEvent[] }) {
  const { t } = useI18n()
  const mine = useMemo(() => events.filter((e) => e.experiment_id === experimentId), [events, experimentId])
  const model = useSessionModel(mine)
  const call = model.pending ?? model.calls[model.calls.length - 1] ?? null
  const action = call ? upper(call.desc.text) : t('work.choosing')
  return (
    <p className="mx-auto mt-1 w-full max-w-[620px] text-center text-[15px] leading-snug text-balance">
      <span className="font-mono text-[11px] font-medium tracking-wider text-live uppercase">{t('work.agent')}</span>{' '}
      <span className={model.pending ? 'font-medium' : 'text-muted-foreground'}>{action}</span>
      <span className="text-muted-foreground"> · </span>
      <a href={href('sessione', { id: String(experimentId) })} className="cursor-pointer font-medium whitespace-nowrap text-live underline-offset-4 hover:underline">
        {t('work.session', { id: experimentId })} →
      </a>
    </p>
  )
}
