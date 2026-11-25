import { useI18n } from '@/i18n/context'
import type { Overview } from '@/lib/api'
import { cn } from '@/lib/utils'
import { PHASES } from './format'

type Ready = Extract<Overview, { ready: true }>

export function TopBar({ data, connected }: { data: Ready; connected: boolean }) {
  const { t } = useI18n()
  const phaseIndex = Math.max(0, PHASES.indexOf(data.phase))
  const phase = PHASES[phaseIndex] ?? 'genesis'
  const champion = data.champion.id
  const live = connected && data.agent !== 'paused'
  return (
    <header className="col-span-full flex flex-wrap items-center gap-x-4 gap-y-2">
      <span className="text-[17px] font-bold tracking-tight">darwin-chess</span>
      <span className="flex basis-full items-baseline gap-2.5 sm:basis-auto sm:border-l sm:pl-4">
        <b className="text-[22px] font-semibold tracking-tight">{t('top.generation', { n: champion })}</b>
        <span className="text-[13px] text-muted-foreground">
          {champion === 0 ? t('top.noChampion') : t('top.racing', { next: champion + 1 })}
        </span>
      </span>
      <span
        className={cn(
          'inline-flex h-[26px] items-center gap-[7px] rounded-full px-[11px] text-xs font-semibold',
          live ? 'bg-bad/15 text-bad' : 'bg-muted text-muted-foreground',
        )}
      >
        <i className={cn('size-[7px] rounded-full bg-current', live && 'animate-pulse')} />
        {!connected ? t('top.disconnected') : data.agent === 'paused' ? t('agent.paused') : t('top.live')}
      </span>
      <span className="flex basis-full items-center gap-2.5 text-[13px] text-muted-foreground sm:ml-auto sm:basis-auto">
        <span className="flex gap-1" aria-hidden>
          {PHASES.map((p, i) => (
            <i key={p} className={cn('h-1 w-[18px] rounded-sm', i <= phaseIndex ? 'bg-live' : 'bg-border')} />
          ))}
        </span>
        <span>
          {t('top.phase', { i: phaseIndex + 1, n: PHASES.length })} ·{' '}
          <b className="font-semibold text-foreground">{t(`phase.${phase}`)}</b>
        </span>
      </span>
    </header>
  )
}
