import { pickText, useI18n } from '@/i18n/context'
import { LangBadge } from '@/i18n/parts'
import type { Experiment, Overview } from '@/lib/api'
import { cn } from '@/lib/utils'
import { failureText } from './format'
import { JobCard } from './job-card'

type Ready = Extract<Overview, { ready: true }>

const card = 'rounded-[18px] bg-card p-5 shadow-[inset_0_0_0_1px_var(--border)]'
const LLR_BOUND = 2.944

export function SideCards({ data }: { data: Ready }) {
  const shown = data.current?.status === 'running' || data.current?.status === 'judging'
    ? data.previous
    : data.current
  return (
    <aside className="order-2 grid min-w-0 content-start gap-3.5 lg:order-none">
      <VerdictCard experiment={shown} judging={data.current?.status === 'judging' ? data.current : null} />
      <JobCard jobs={data.jobs} />
      <SpendCard spend={data.spend} />
    </aside>
  )
}

function VerdictCard({ experiment, judging }: { experiment: Experiment | null; judging: Experiment | null }) {
  const i18n = useI18n()
  const { t, label, lang, f } = i18n
  if (judging) {
    const hypothesis = pickText(lang, { en: judging.hypothesis, it: judging.hypothesis_it })
    return (
      <section className={card}>
        <p className="mb-2.5 text-[13px] text-muted-foreground">{t('verdict.judging')}</p>
        <p className="mb-3.5 text-[22px] font-semibold tracking-tight">{t('player.candidate', { id: judging.id })}</p>
        {hypothesis && (
          <p className="text-xs leading-relaxed text-muted-foreground">
            {hypothesis.fallback && <LangBadge lang={hypothesis.lang} className="mr-1.5" />}
            <span lang={hypothesis.lang}>{hypothesis.text}</span>
          </p>
        )}
      </section>
    )
  }
  if (!experiment) {
    return (
      <section className={card}>
        <p className="mb-2.5 text-[13px] text-muted-foreground">{t('verdict.last')}</p>
        <p className="text-[22px] font-semibold tracking-tight">{t('verdict.none')}</p>
      </section>
    )
  }
  const match = experiment.match
  const accepted = experiment.status === 'accepted'
  const question = match
    ? match.opponent === 'random'
      ? t('verdict.question.random')
      : t('verdict.question.champion')
    : t('verdict.question.rules')
  const failed = experiment.gates.find((g) => !g.passed)
  return (
    <section className={card}>
      <p className="mb-2.5 text-[13px] text-muted-foreground">{question}</p>
      <p className={cn('mb-3.5 text-[22px] font-semibold tracking-tight', accepted ? 'text-good' : 'text-bad')}>
        {accepted ? t('verdict.yes') : failed ? t('verdict.stoppedAt', { gate: label('gate', failed.gate) }) : t('verdict.no')}
      </p>
      {match?.llr != null && <LlrBar llr={match.llr} />}
      {match && (
        <p className="mt-2.5 text-xs leading-relaxed text-muted-foreground">
          <span className="text-foreground">{f.num(match.wins + match.draws + match.losses)}</span> {t('verdict.games')} ·{' '}
          <span className="text-foreground">{f.num(Math.round(match.elo ?? 0))}</span> Elo ·{' '}
          {t('verdict.wdl', { w: match.wins, d: match.draws, l: match.losses })}
        </p>
      )}
      {failed && !match && (
        <p className="mt-2.5 text-xs leading-relaxed text-muted-foreground">{failureText(i18n, failed.detail)}</p>
      )}
      <div className="mt-3 flex flex-wrap gap-3.5 text-xs text-muted-foreground">
        {experiment.gates.map((g) => (
          <span key={g.gate}>
            <span className={g.passed ? 'text-good' : 'text-bad'}>{g.passed ? '✓' : '✗'}</span> {label('gate', g.gate)}
          </span>
        ))}
      </div>
    </section>
  )
}

function LlrBar({ llr }: { llr: number }) {
  const { t, f } = useI18n()
  const share = Math.max(-1, Math.min(1, llr / LLR_BOUND))
  return (
    <div className="mt-3">
      <div className="relative h-2 rounded-full bg-muted">
        <span className="absolute top-0 left-1/2 h-2 w-px bg-border" />
        <span className={cn('absolute top-0 h-2 rounded-full', share >= 0 ? 'bg-good' : 'bg-bad')}
              style={{ left: `${share >= 0 ? 50 : 50 + share * 50}%`, width: `${Math.abs(share) * 50}%` }} />
      </div>
      <div className="mt-1.5 flex justify-between font-mono text-[11px] text-muted-foreground">
        <span>{t('verdict.llrReject')}</span><span>LLR {f.num(llr)}</span><span>{t('verdict.llrAccept')}</span>
      </div>
    </div>
  )
}

function SpendCard({ spend }: { spend: Ready['spend'] }) {
  const { t, tn, f } = useI18n()
  const share = Math.min(1, spend.usd / spend.budget)
  const full = spend.usd >= spend.budget
  return (
    <section className={card}>
      <p className="mb-2.5 text-[13px] text-muted-foreground">{t('spend.title')}</p>
      <p className="flex items-baseline gap-2.5">
        <b className="text-[32px] leading-none font-semibold tracking-tight tabular-nums">{f.money(spend.usd)}</b>
        <span className="font-mono text-[13px] text-muted-foreground">{t('spend.of', { budget: f.money(spend.budget) })}</span>
      </p>
      <div className="mt-3 h-1.5 rounded-full bg-muted">
        <i className={cn('block h-1.5 rounded-full', full ? 'bg-bad' : 'bg-live')} style={{ width: `${share * 100}%` }} />
      </div>
      <p className="mt-2.5 text-xs text-muted-foreground">
        {full ? t('spend.full') : t('spend.sessions', { sessions: tn('count.sessions', spend.sessions) })}
      </p>
    </section>
  )
}
