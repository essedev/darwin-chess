import { useI18n } from '@/i18n/context'
import type { Overview } from '@/lib/api'
import { cn } from '@/lib/utils'
import { PHASES } from './format'

type Ready = Extract<Overview, { ready: true }>

/** The generation in office, what is racing to replace it, whether we are live, the phases by name. */
export function TopBar({ data, connected }: { data: Ready; connected: boolean }) {
  const { t } = useI18n()
  const phaseIndex = Math.max(0, PHASES.indexOf(data.phase))
  const champion = data.champion.id
  const racing = data.on_trial ?? (data.current && ['running', 'judging'].includes(data.current.status) ? data.current : null)
  const live = connected && data.agent !== 'paused'
  return (
    <header className="col-span-full flex flex-wrap items-center gap-x-4 gap-y-2.5">
      <div className="flex flex-col gap-0.5 sm:flex-row sm:items-baseline sm:gap-3">
        <h1 className="text-[24px] font-semibold tracking-tight">{t('top.generation', { n: champion })}</h1>
        <p className="text-[14px] text-muted-foreground">
          {champion === 0
            ? t('top.noChampion')
            : racing
              ? t('top.racing', { id: racing.id, next: champion + 1 })
              : t('top.waiting')}
        </p>
      </div>
      <span
        className={cn(
          'inline-flex h-[24px] items-center gap-[7px] rounded-full px-[10px] text-xs font-semibold',
          live ? 'bg-bad/15 text-bad' : 'bg-muted text-muted-foreground',
        )}
      >
        <i className={cn('size-[7px] rounded-full bg-current', live && 'animate-pulse')} />
        {!connected ? t('top.disconnected') : data.agent === 'paused' ? t('agent.paused') : t('top.live')}
      </span>
      <ol aria-label={t('top.phases')} className="flex items-center text-[12px] text-muted-foreground sm:ml-auto">
        {PHASES.map((p, i) => (
          <li
            key={p}
            aria-current={i === phaseIndex ? 'step' : undefined}
            className={cn(
              'items-center gap-1.5 whitespace-nowrap',
              i === phaseIndex ? 'flex font-medium text-foreground' : 'hidden sm:flex',
              i > 0 && 'sm:before:mx-2 sm:before:h-px sm:before:w-3.5 sm:before:bg-border sm:before:content-[""]',
            )}
          >
            <i className={cn('size-1.5 rounded-full', i < phaseIndex ? 'bg-muted-foreground' : i === phaseIndex ? 'bg-live' : 'bg-border')} />
            {t(`phase.${p}`)}
          </li>
        ))}
      </ol>
    </header>
  )
}
