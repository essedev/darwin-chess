import { failureText, plainText } from '@/features/live/format'
import { type I18n, pickText, useI18n } from '@/i18n/context'
import { LangBadge } from '@/i18n/parts'
import type { ExperimentRow as Experiment } from '@/lib/api'
import { href } from '@/lib/use-route'
import { cn } from '@/lib/utils'

const TONE: Record<string, string> = {
  accepted: 'text-good',
  rejected: 'text-bad',
  error: 'text-bad',
  abandoned: 'text-bad',
  budget_stop: 'text-bad',
  running: 'text-live',
  judging: 'text-live',
}

export function ExperimentRow({ experiment: e }: { experiment: Experiment }) {
  const i18n = useI18n()
  const { t, label, lang, f } = i18n
  const reflection = e.kind === 'reflection'
  const hypothesis = pickText(lang, { en: e.hypothesis, it: e.hypothesis_it })
  const reason = rejection(i18n, e)
  return (
    <li
      className={cn(
        'grid gap-1.5 rounded-[14px] px-4 py-3.5',
        reflection ? 'border border-dashed' : 'bg-card shadow-[inset_0_0_0_1px_var(--border)]',
      )}
    >
      <p className="flex flex-wrap items-baseline gap-x-2.5 gap-y-0.5 text-[12px]">
        <span className="font-mono text-[13px] font-medium">#{e.id}</span>
        {reflection ? (
          <span className="rounded-full bg-muted px-2 py-px font-medium text-muted-foreground">{t('experiment.reflection')}</span>
        ) : (
          <span className={cn('font-semibold', TONE[e.status] ?? 'text-muted-foreground')}>{label('status', e.status)}</span>
        )}
        <time dateTime={e.created_at} className="text-muted-foreground">{f.dateTime(e.created_at)}</time>
        {e.cost_usd !== null && (
          <span className="ml-auto font-mono text-muted-foreground tabular-nums" title={t('experiment.costTitle')}>
            {f.preciseMoney(e.cost_usd)}
          </span>
        )}
      </p>
      <p className={cn('text-[14px] leading-snug text-pretty', !hypothesis && reflection && 'text-muted-foreground italic')}
         lang={hypothesis?.lang}>
        {hypothesis?.fallback && <LangBadge lang={hypothesis.lang} className="mr-1.5" />}
        {hypothesis
          ? plainText(hypothesis.text)
          : reflection
            ? t('experiment.reflectionText')
            : t('experiment.noHypothesis')}
      </p>
      {reason && (
        <p className="text-[13px] leading-relaxed text-muted-foreground">
          <span className="font-medium text-bad">{t('experiment.stoppedAt', { gate: reason.gate })}</span>
          {reason.why && `: ${reason.why}`}
        </p>
      )}
      {e.candidate_commit && (
        <a
          href={href('codice', { diff: `exp-${e.id}` })}
          className="w-fit cursor-pointer text-[13px] font-medium text-live underline-offset-4 hover:underline"
        >
          {t('experiment.seeChanges')}
        </a>
      )}
    </li>
  )
}

/** Which gate stopped it and why, in plain words; null when it was not rejected. */
function rejection(i18n: I18n, e: Experiment): { gate: string; why: string } | null {
  const { t, tn, label, f } = i18n
  if (!e.rejected_at_gate) return null
  const gate = label('gate', e.rejected_at_gate)
  const failed = e.gates.find((g) => g.gate === e.rejected_at_gate)
  if (e.rejected_at_gate === 'match' && e.match) {
    const m = e.match
    const elo = m.elo === null ? '' : `${f.signed(m.elo)}${m.elo_error === null ? '' : ` ± ${f.num(Math.round(m.elo_error))}`} Elo `
    const why = t('experiment.matchWhy', {
      elo,
      opponent: opponent(i18n, m.opponent),
      games: tn('count.games', m.wins + m.draws + m.losses),
      wdl: t('matches.wdl', { w: m.wins, d: m.draws, l: m.losses }),
    })
    return { gate, why }
  }
  return { gate, why: failed ? failureText(i18n, failed.detail, failed.gate) : '' }
}

function opponent({ t }: I18n, name: string): string {
  if (name === 'random') return t('opponent.random')
  if (name === 'champion') return t('opponent.champion')
  const gen = /^gen-(\d+)$/.exec(name)
  return gen ? t('opponent.generation', { gen: gen[1] ?? '' }) : name
}
