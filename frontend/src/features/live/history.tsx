import { pickText, useI18n } from '@/i18n/context'
import { LangBadge, Rich } from '@/i18n/parts'
import type { LichessPerformance, Overview } from '@/lib/api'
import { cn } from '@/lib/utils'
import { eloSeries } from './format'
import { Spark } from './spark'

type Ready = Extract<Overview, { ready: true }>

const card = 'rounded-[18px] bg-card p-5 shadow-[inset_0_0_0_1px_var(--border)]'

export function History({ data, lichess }: { data: Ready; lichess: LichessPerformance | undefined }) {
  const { t, tn, label, lang, f } = useI18n()
  const { absolute, points } = eloSeries(data.generations)
  const best = points.at(-1)
  const promoted = data.generations.filter((g) => g.id >= 1)
  const current = data.current
  const currentText = current && pickText(lang, { en: current.hypothesis, it: current.hypothesis_it })
  return (
    <aside className="order-3 grid min-w-0 content-start gap-3.5 lg:order-none">
      <section className={card}>
        <p className="mb-2.5 text-[13px] text-muted-foreground">{t('history.title')}</p>
        {best ? (
          <>
            <p className="flex items-baseline gap-2.5">
              <b className="text-[44px] leading-none font-semibold tracking-tight tabular-nums">{f.num(best.elo)}</b>
              <span className="font-mono text-[13px] text-muted-foreground">
                {absolute ? 'Elo' : t('history.eloRandom')} · gen-{best.id}
              </span>
            </p>
            <Spark points={points} />
          </>
        ) : (
          <p className="text-[22px] font-semibold tracking-tight">{t('history.noChampion')}</p>
        )}
        {lichess && (
          <p className="mt-3 text-xs text-muted-foreground">
            <Rich
              text={t('history.lichess')}
              values={{
                performance: <span className="font-medium text-foreground tabular-nums">{lichess.performance}</span>,
                games: tn('count.games', lichess.games),
                gen: data.champion.id,
              }}
            />
          </p>
        )}
      </section>
      <ol className="grid gap-0.5">
        {current && (
          <Row tag={`#${current.id}`} now title={currentText?.text ?? t('history.working')}
               badge={currentText?.fallback ? currentText.lang : null}
               subtitle={label('status', current.status)} />
        )}
        {[...promoted].reverse().map((g) => {
          const text = pickText(lang, { en: g.hypothesis, it: g.hypothesis_it })
          const gain = g.id === 1 ? t('history.beatsRandom') : `+${f.num(Math.round(g.elo_vs_parent ?? 0))} Elo`
          return (
            <Row key={g.id} tag={`gen-${g.id}`} title={text?.text ?? ''} badge={text?.fallback ? text.lang : null}
                 subtitle={`${gain} · ${tn('count.attempts', g.tried)}`}
                 value={points.find((p) => p.id === g.id)?.elo} />
          )
        })}
        <Row tag="gen-0" title={t('history.seed')}
             subtitle={data.generations[0] ? f.shortDate(data.generations[0].created_at) : ''} />
      </ol>
      <p className="px-2.5 text-xs text-muted-foreground">
        {t('history.totals', { attempts: tn('count.attempts', data.experiments.total), promoted: tn('count.promoted', promoted.length) })}
      </p>
    </aside>
  )
}

function Row(props: { tag: string; title: string; subtitle: string; value?: number; now?: boolean; badge?: 'it' | 'en' | null }) {
  const { f } = useI18n()
  return (
    <li className={cn('grid grid-cols-[52px_minmax(0,1fr)_auto] items-center gap-2.5 rounded-[10px] px-2.5 py-[9px]', props.now && 'bg-live/12')}>
      <span className={cn('font-mono text-xs font-medium text-muted-foreground', props.now && 'text-live')}>{props.tag}</span>
      <span className="min-w-0">
        <span className="flex min-w-0 items-center gap-1.5">
          <b className="block min-w-0 truncate text-[13px] font-medium" title={props.title} lang={props.badge ?? undefined}>{props.title}</b>
          {props.badge && <LangBadge lang={props.badge} />}
        </span>
        <span className="block truncate text-[11px] text-muted-foreground">{props.subtitle}</span>
      </span>
      <span className="font-mono text-[13px] font-medium tabular-nums">{props.value !== undefined ? f.num(props.value) : ''}</span>
    </li>
  )
}
