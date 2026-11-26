import { Fact } from '@/components/expand-row'
import { card } from '@/components/page'
import { failureText, plainText, titleText } from '@/features/live/format'
import { pickText, useI18n } from '@/i18n/context'
import { LangBadge } from '@/i18n/parts'
import type { SessionDetail } from '@/lib/api'
import { href } from '@/lib/use-route'
import { cn } from '@/lib/utils'

const link = 'cursor-pointer font-medium text-live underline-offset-4 hover:underline'
const WHY = ['stale', 'error', 'abandoned', 'budget_stop'] as const

/** How the session ended: the verdict of its candidate, or why there is none. */
export function SessionEnd({ session: s }: { session: SessionDetail }) {
  const i18n = useI18n()
  const { t, tn, f, label, lang } = i18n
  if (s.status === 'running') return null
  const reflection = s.kind === 'reflection'
  const title = titleText(lang, s.title, { en: s.hypothesis, it: s.hypothesis_it })
  const hypothesis = pickText(lang, { en: s.hypothesis, it: s.hypothesis_it })
  const failed = s.rejected_at_gate ? s.gates.find((g) => g.gate === s.rejected_at_gate) : undefined
  const m = s.match
  const why = WHY.find((x) => x === s.status)
  const headline = reflection ? t('session.end.reflected')
    : s.status === 'judging' ? t('session.end.judging')
    : s.generation_id != null ? t('session.end.accepted', { gen: s.generation_id })
    : s.status === 'rejected' ? t('session.end.rejected')
    : why ? t(`experiment.why.${why}`)
    : label('status', s.status)
  const tone = s.generation_id != null ? 'text-good' : s.status === 'rejected' || s.status === 'error' ? 'text-bad' : ''
  return (
    <section aria-labelledby="session-end" className={cn(card, 'grid gap-3 text-[14px]')}>
      <h2 id="session-end" className="panel-label">{t('session.end.title')}</h2>
      <p className={cn('text-[17px] font-semibold tracking-tight text-balance', tone)}>{headline}</p>
      {title && !reflection && (
        <p className="font-medium" lang={title.lang}>
          #{s.id} {title.text}
        </p>
      )}
      {hypothesis && (
        <p className="max-w-[72ch] text-muted-foreground">
          <b className="block font-semibold text-foreground">{t('detail.hypothesis')}</b>
          {hypothesis.fallback && <LangBadge lang={hypothesis.lang} className="mr-1.5" />}
          <span lang={hypothesis.lang}>{plainText(hypothesis.text)}</span>
        </p>
      )}
      {s.rejected_at_gate && s.rejected_at_gate !== 'match' && (
        <p className="text-bad">
          {t('experiment.stoppedAt', { gate: label('gate', s.rejected_at_gate) })}
          {failed && `: ${failureText(i18n, failed.detail, failed.gate)}`}
        </p>
      )}
      {m && (
        <p className="flex flex-wrap gap-x-4 gap-y-1">
          <Fact label={t('detail.match')}>{tn('count.games', m.wins + m.draws + m.losses)}</Fact>
          <Fact label={t('detail.score')}>{t('verdict.wdl', { w: f.num(m.wins), d: f.num(m.draws), l: f.num(m.losses) })}</Fact>
          {m.elo !== null && (
            <Fact label={t('detail.difference')}>
              {f.signed(m.elo)}
              {m.elo_error === null ? '' : ` ± ${f.num(Math.round(m.elo_error))}`} Elo
            </Fact>
          )}
        </p>
      )}
      <p className="flex flex-wrap gap-x-4 gap-y-1.5 text-[13px]">
        {s.candidate_commit && <a href={href('codice', { diff: `exp-${s.id}` })} className={link}>{t('experiment.seeChanges')}</a>}
        {reflection ? (
          <a href={href('mente')} className={link}>{t('session.end.mind')}</a>
        ) : (
          <a href={href('evoluzione')} className={link}>{t('session.end.attempts')}</a>
        )}
      </p>
    </section>
  )
}
