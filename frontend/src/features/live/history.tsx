import type { Overview } from '@/lib/api'
import { cn } from '@/lib/utils'
import { STATUS, eloSeries, num } from './format'
import { Spark } from './spark'

type Ready = Extract<Overview, { ready: true }>

const card = 'rounded-[18px] bg-card p-5 shadow-[inset_0_0_0_1px_var(--border)]'

export function History({ data }: { data: Ready }) {
  const { absolute, points } = eloSeries(data.generations)
  const best = points.at(-1)
  const promoted = data.generations.filter((g) => g.id >= 1)
  const current = data.current
  return (
    <aside className="order-3 grid min-w-0 content-start gap-3.5 lg:order-none">
      <section className={card}>
        <p className="mb-2.5 text-[13px] text-muted-foreground">Come sta andando</p>
        {best ? (
          <>
            <p className="flex items-baseline gap-2.5">
              <b className="text-[44px] leading-none font-semibold tracking-tight tabular-nums">{num(best.elo)}</b>
              <span className="font-mono text-[13px] text-muted-foreground">{absolute ? 'Elo' : 'Elo sul casuale'} · gen-{best.id}</span>
            </p>
            <Spark points={points} />
          </>
        ) : (
          <p className="text-[22px] font-semibold tracking-tight">Nessun campione ancora</p>
        )}
      </section>
      <ol className="grid gap-0.5">
        {current && (
          <Row tag={`#${current.id}`} now title={current.hypothesis ?? 'L’agente sta lavorando'}
               subtitle={STATUS[current.status] ?? current.status} />
        )}
        {[...promoted].reverse().map((g) => (
          <Row key={g.id} tag={`gen-${g.id}`} title={g.hypothesis ?? ''}
               subtitle={`${g.id === 1 ? 'batte il casuale' : `+${num(Math.round(g.elo_vs_parent ?? 0))} Elo`} · ${g.tried} tentativi`}
               value={points.find((p) => p.id === g.id)?.elo} />
        ))}
        <Row tag="gen-0" title="Il seme vuoto" subtitle={seedDate(data.generations[0]?.created_at)} />
      </ol>
      <p className="px-2.5 text-xs text-muted-foreground">
        {data.experiments.total} tentativi, {promoted.length} promossi
      </p>
    </aside>
  )
}

function seedDate(iso: string | undefined) {
  return iso ? new Date(iso).toLocaleDateString('it-IT', { day: 'numeric', month: 'short' }) : ''
}

function Row(props: { tag: string; title: string; subtitle: string; value?: number; now?: boolean }) {
  return (
    <li className={cn('grid grid-cols-[52px_minmax(0,1fr)_auto] items-center gap-2.5 rounded-[10px] px-2.5 py-[9px]', props.now && 'bg-live/12')}>
      <span className={cn('font-mono text-xs font-medium text-muted-foreground', props.now && 'text-live')}>{props.tag}</span>
      <span className="min-w-0">
        <b className="block truncate text-[13px] font-medium" title={props.title}>{props.title}</b>
        <span className="block truncate text-[11px] text-muted-foreground">{props.subtitle}</span>
      </span>
      <span className="font-mono text-[13px] font-medium tabular-nums">{props.value !== undefined ? num(props.value) : ''}</span>
    </li>
  )
}
