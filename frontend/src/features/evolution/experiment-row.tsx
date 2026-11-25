import { ExpandRow, Fact } from '@/components/expand-row'
import { failureText, plainText, titleText } from '@/features/live/format'
import { type I18n, pickText, useI18n } from '@/i18n/context'
import { LangBadge } from '@/i18n/parts'
import type { ExperimentRow as Experiment } from '@/lib/api'
import { href } from '@/lib/use-route'
import { cn } from '@/lib/utils'

const TONE: Record<string, string> = {
  accepted: 'bg-good/12 text-good',
  rejected: 'bg-bad/12 text-bad',
  error: 'bg-bad/12 text-bad',
  budget_stop: 'bg-bad/12 text-bad',
  running: 'bg-live/14 text-live',
  judging: 'bg-live/14 text-live',
}

/** One line per experiment (number, title, outcome); its story opens in place. */
export function ExperimentRow({ experiment: e }: { experiment: Experiment }) {
  const i18n = useI18n()
  const { t, label, lang, f } = i18n
  const reflection = e.kind === 'reflection'
  const title = titleText(lang, e.title, { en: e.hypothesis, it: e.hypothesis_it })
  const status = reflection ? t('experiment.reflection') : label('status', e.status)
  return (
    <ExpandRow
      columns="grid-cols-[40px_minmax(0,1fr)_auto_16px]"
      line={
        <>
          <span className="font-mono text-[13px] font-medium text-muted-foreground">#{e.id}</span>
          <span className="min-w-0">
            <b className={cn('block truncate text-[14px] font-medium', !title && 'text-muted-foreground')} lang={title?.lang}>
              {title?.text ?? (reflection ? t('experiment.reflectionTitle') : t('experiment.noHypothesis'))}
            </b>
            <span className="block truncate text-[12px] text-muted-foreground">{summary(i18n, e) ?? f.dateTime(e.created_at)}</span>
          </span>
          <span className={cn('rounded-full px-2 py-px text-[12px] font-semibold whitespace-nowrap', TONE[e.status] ?? 'bg-muted text-muted-foreground')}>
            {status}
          </span>
        </>
      }
    >
      <Details experiment={e} />
    </ExpandRow>
  )
}

/** The second line: what became of it, in a few words; null to show the date instead. */
function summary(i18n: I18n, e: Experiment): string | null {
  const { t, label, f } = i18n
  if (e.generation_id != null) return t('experiment.became', { gen: e.generation_id })
  if (!e.rejected_at_gate) return null
  const m = e.match
  const elo = e.rejected_at_gate === 'match' && m?.elo != null
    ? ` · ${f.signed(m.elo)}${m.elo_error == null ? '' : ` ± ${f.num(Math.round(m.elo_error))}`}`
    : ''
  return `${t('experiment.stoppedAtShort', { gate: label('gate', e.rejected_at_gate) })}${elo}`
}

function Details({ experiment: e }: { experiment: Experiment }) {
  const i18n = useI18n()
  const { t, tn, label, lang, f } = i18n
  const hypothesis = pickText(lang, { en: e.hypothesis, it: e.hypothesis_it })
  const m = e.match
  const failed = e.rejected_at_gate ? e.gates.find((g) => g.gate === e.rejected_at_gate) : undefined
  return (
    <>
      {hypothesis ? (
        <p>
          <b className="block font-semibold">{t('detail.hypothesis')}</b>
          {hypothesis.fallback && <LangBadge lang={hypothesis.lang} className="mr-1.5" />}
          <span lang={hypothesis.lang}>{plainText(hypothesis.text)}</span>
        </p>
      ) : (
        e.kind === 'reflection' && <p className="text-muted-foreground">{t('experiment.reflectionText')}</p>
      )}
      {m && (
        <p className="flex flex-wrap gap-x-4 gap-y-1">
          <Fact label={t('detail.match')}>{tn('count.games', m.wins + m.draws + m.losses)}</Fact>
          <Fact label={t('detail.score')}>{t('verdict.wdl', { w: f.num(m.wins), d: f.num(m.draws), l: f.num(m.losses) })}</Fact>
          <Fact label={t('detail.against')}>{opponent(i18n, m.opponent)}</Fact>
          {m.elo !== null && (
            <Fact label={t('detail.difference')}>
              {f.signed(m.elo)}{m.elo_error === null ? '' : ` ± ${f.num(Math.round(m.elo_error))}`} Elo
            </Fact>
          )}
        </p>
      )}
      {e.rejected_at_gate && e.rejected_at_gate !== 'match' && (
        <p className="text-bad">
          {t('experiment.stoppedAt', { gate: label('gate', e.rejected_at_gate) })}
          {failed && `: ${failureText(i18n, failed.detail, failed.gate)}`}
        </p>
      )}
      {['stale', 'error', 'abandoned', 'budget_stop'].includes(e.status) && (
        <p className="text-muted-foreground">{t(`experiment.why.${e.status as 'stale' | 'error' | 'abandoned' | 'budget_stop'}`)}</p>
      )}
      <p className="flex flex-wrap items-center gap-x-4 gap-y-1">
        {e.cost_usd !== null && <Fact label={t('detail.cost')}>{f.preciseMoney(e.cost_usd)}</Fact>}
        <Fact label={t('detail.when')}>{f.dateTime(e.created_at)}</Fact>
        {e.candidate_commit && (
          <a href={href('codice', { diff: `exp-${e.id}` })} className="cursor-pointer font-medium text-live underline-offset-4 hover:underline">
            {t('experiment.seeChanges')}
          </a>
        )}
      </p>
    </>
  )
}

function opponent({ t }: I18n, name: string): string {
  if (name === 'random') return t('opponent.random')
  if (name === 'champion') return t('opponent.champion')
  const gen = /^gen-(\d+)$/.exec(name)
  return gen ? t('opponent.generation', { gen: gen[1] ?? '' }) : name
}
