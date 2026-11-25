import { card } from '@/components/page'
import { useI18n } from '@/i18n/context'
import type { Lab } from '@/lib/api'
import { cn } from '@/lib/utils'

/** The running totals: what it cost, how many attempts, how many tokens, how many games. */
export function LabNumbers({ totals }: { totals: Lab['totals'] }) {
  const { t, f } = useI18n()
  const tiles: { label: string; value: string; note?: string }[] = [
    { label: t('lab.tile.spend'), value: f.preciseMoney(totals.spend_usd), note: t('lab.tile.spendNote') },
    { label: t('lab.tile.sessions'), value: f.num(totals.sessions) },
    {
      label: t('lab.tile.attempts'),
      value: f.num(totals.iterations),
      note: t('lab.tile.attemptsNote', { accepted: f.num(totals.accepted), rejected: f.num(totals.rejected) }),
    },
    { label: t('lab.tile.calls'), value: f.num(totals.llm_calls) },
    {
      label: t('lab.tile.read'),
      value: f.compact(totals.input_tokens + totals.cached_tokens),
      note: t('lab.tile.readNote', { cached: f.compact(totals.cached_tokens) }),
    },
    { label: t('lab.tile.written'), value: f.compact(totals.output_tokens) },
    { label: t('lab.tile.games'), value: f.num(totals.lichess_games) },
  ]
  return (
    <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-4">
      {tiles.map((tile) => (
        <li key={tile.label} className={cn(card, 'grid content-start gap-1 p-4')}>
          <span className="text-[13px] text-muted-foreground">{tile.label}</span>
          <b className="text-[26px] leading-tight font-semibold tracking-tight tabular-nums">{tile.value}</b>
          {tile.note && <span className="text-[12px] text-muted-foreground">{tile.note}</span>}
        </li>
      ))}
    </ul>
  )
}

/** One bar per promoted generation: how much the attempts that led to it cost. */
export function CostPerGeneration({ rows }: { rows: Lab['cost_per_generation'] }) {
  const { t, f } = useI18n()
  const max = Math.max(...rows.map((r) => r.usd), 0)
  return (
    <section className={cn(card, 'grid min-w-0 content-start gap-3')}>
      <header className="grid gap-0.5">
        <h2 className="text-[17px] font-semibold tracking-tight">{t('lab.cost.title')}</h2>
        <p className="text-[13px] text-muted-foreground">{t('lab.cost.hint')}</p>
      </header>
      {rows.length === 0 ? (
        <p className="py-4 text-center text-[14px] text-muted-foreground">{t('lab.cost.none')}</p>
      ) : (
        <ol className="grid gap-1.5">
          {rows.map((r) => (
            <li key={r.generation} className="grid grid-cols-[56px_minmax(0,1fr)_72px] items-center gap-3 text-[13px]">
              <span className="font-mono text-muted-foreground">gen-{r.generation}</span>
              <span className="h-2 rounded-full bg-muted">
                <i className="block h-2 rounded-full bg-live" style={{ width: `${max > 0 ? (r.usd / max) * 100 : 0}%` }} />
              </span>
              <span className="text-right font-mono tabular-nums">{f.preciseMoney(r.usd)}</span>
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}
