import type { Overview } from '@/lib/api'
import { cn } from '@/lib/utils'
import { PHASES } from './format'

type Ready = Extract<Overview, { ready: true }>

export function TopBar({ data, connected }: { data: Ready; connected: boolean }) {
  const phaseIndex = PHASES.findIndex((p) => p.key === data.phase)
  const phase = PHASES[phaseIndex] ?? PHASES[0]
  const champion = data.champion.id
  const live = connected && data.agent !== 'paused'
  return (
    <header className="col-span-full flex flex-wrap items-center gap-x-4 gap-y-2">
      <span className="text-[17px] font-bold tracking-tight">darwin-chess</span>
      <span className="flex basis-full items-baseline gap-2.5 sm:basis-auto sm:border-l sm:pl-4">
        <b className="text-[22px] font-semibold tracking-tight">Generazione {champion}</b>
        <span className="text-[13px] text-muted-foreground">
          {champion === 0
            ? 'nessun campione, si scrivono le regole'
            : `in gara il candidato per la ${champion + 1}`}
        </span>
      </span>
      <span
        className={cn(
          'inline-flex h-[26px] items-center gap-[7px] rounded-full px-[11px] text-xs font-semibold',
          live ? 'bg-bad/15 text-bad' : 'bg-muted text-muted-foreground',
        )}
      >
        <i className={cn('size-[7px] rounded-full bg-current', live && 'animate-pulse')} />
        {!connected ? 'Connessione persa' : data.agent === 'paused' ? 'Agente in pausa' : 'In diretta'}
      </span>
      <span className="flex basis-full items-center gap-2.5 text-[13px] text-muted-foreground sm:ml-auto sm:basis-auto">
        <span className="flex gap-1" aria-hidden>
          {PHASES.map((p, i) => (
            <i key={p.key} className={cn('h-1 w-[18px] rounded-sm', i <= phaseIndex ? 'bg-live' : 'bg-border')} />
          ))}
        </span>
        <span>
          Fase {phaseIndex + 1} di {PHASES.length} · <b className="font-semibold text-foreground">{phase?.name}</b>
        </span>
      </span>
    </header>
  )
}
