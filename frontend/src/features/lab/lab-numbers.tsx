import { card } from '@/components/page'
import { num, preciseMoney } from '@/features/live/format'
import type { Lab } from '@/lib/api'
import { cn } from '@/lib/utils'

const compact = new Intl.NumberFormat('it-IT', { notation: 'compact', maximumFractionDigits: 1 })

/** The running totals: what it cost, how many attempts, how many tokens, how many games. */
export function LabNumbers({ totals }: { totals: Lab['totals'] }) {
  const tiles: { label: string; value: string; note?: string }[] = [
    { label: 'Spesa totale', value: preciseMoney(totals.spend_usd), note: 'in chiamate al modello' },
    { label: 'Sessioni di lavoro', value: num(totals.sessions) },
    {
      label: 'Tentativi',
      value: num(totals.iterations),
      note: `${num(totals.accepted)} promossi · ${num(totals.rejected)} scartati`,
    },
    { label: 'Chiamate al modello', value: num(totals.llm_calls) },
    {
      label: 'Token letti',
      value: compact.format(totals.input_tokens + totals.cached_tokens),
      note: `di cui ${compact.format(totals.cached_tokens)} dalla cache`,
    },
    { label: 'Token scritti', value: compact.format(totals.output_tokens) },
    { label: 'Partite su Lichess', value: num(totals.lichess_games) },
  ]
  return (
    <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-4">
      {tiles.map((t) => (
        <li key={t.label} className={cn(card, 'grid content-start gap-1 p-4')}>
          <span className="text-[13px] text-muted-foreground">{t.label}</span>
          <b className="text-[26px] leading-tight font-semibold tracking-tight tabular-nums">{t.value}</b>
          {t.note && <span className="text-[12px] text-muted-foreground">{t.note}</span>}
        </li>
      ))}
    </ul>
  )
}

/** One bar per promoted generation: how much the attempts that led to it cost. */
export function CostPerGeneration({ rows }: { rows: Lab['cost_per_generation'] }) {
  const max = Math.max(...rows.map((r) => r.usd), 0)
  return (
    <section className={cn(card, 'grid min-w-0 content-start gap-3')}>
      <header className="grid gap-0.5">
        <h2 className="text-[17px] font-semibold tracking-tight">Quanto è costata ogni generazione</h2>
        <p className="text-[13px] text-muted-foreground">La spesa di tutti i tentativi, promossi e scartati, che hanno portato a lei.</p>
      </header>
      {rows.length === 0 ? (
        <p className="py-4 text-center text-[14px] text-muted-foreground">Nessuna generazione promossa ancora.</p>
      ) : (
        <ol className="grid gap-1.5">
          {rows.map((r) => (
            <li key={r.generation} className="grid grid-cols-[56px_minmax(0,1fr)_72px] items-center gap-3 text-[13px]">
              <span className="font-mono text-muted-foreground">gen-{r.generation}</span>
              <span className="h-2 rounded-full bg-muted">
                <i className="block h-2 rounded-full bg-live" style={{ width: `${max > 0 ? (r.usd / max) * 100 : 0}%` }} />
              </span>
              <span className="text-right font-mono tabular-nums">{preciseMoney(r.usd)}</span>
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}
