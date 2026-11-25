import { ErrorNote, LoadingNote } from '@/components/page'
import { type I18n, pickText, useI18n } from '@/i18n/context'
import { isClientError, type JudgedMatch, useMatches } from '@/lib/api'
import { cn } from '@/lib/utils'
import { ClampText } from './clamp-text'
import { plainText } from './format'

const card = 'rounded-[18px] bg-card p-5 shadow-[inset_0_0_0_1px_var(--border)]'

const VERDICT: Record<string, { key: 'matches.verdict.h1' | 'matches.verdict.h0' | 'matches.verdict.continue'; tone: string }> = {
  h1: { key: 'matches.verdict.h1', tone: 'bg-good/12 text-good' },
  h0: { key: 'matches.verdict.h0', tone: 'bg-bad/12 text-bad' },
  continue: { key: 'matches.verdict.continue', tone: 'bg-muted text-muted-foreground' },
}

/** The referee's last judged matches, under the board on the Arbitro tab. */
export function JudgedMatches() {
  const { t } = useI18n()
  const matches = useMatches()
  // An API without the endpoint yet answers 404: the section simply is not there.
  if (matches.isError && isClientError(matches.error)) return null
  return (
    <section aria-labelledby="judged-matches" className={card}>
      <h2 id="judged-matches" className="mb-2.5 text-[13px] font-normal text-muted-foreground">{t('matches.title')}</h2>
      {matches.isPending ? (
        <LoadingNote what={t('what.matches')} className="py-3" />
      ) : matches.isError && !matches.data ? (
        <ErrorNote what={t('what.matches')} className="py-3" />
      ) : !matches.data?.length ? (
        <p className="text-[13px]">{t('matches.none')}</p>
      ) : (
        <ol className="grid divide-y">
          {matches.data.map((match) => (
            <Row key={match.id} match={match} />
          ))}
        </ol>
      )}
      {matches.isError && matches.data && <p className="mt-2 text-[12px] text-muted-foreground">{t('list.stale')}</p>}
    </section>
  )
}

function Row({ match: m }: { match: JudgedMatch }) {
  const i18n = useI18n()
  const { t, lang, f } = i18n
  const verdict = m.verdict ? VERDICT[m.verdict] : undefined
  const hypothesis = pickText(lang, { en: m.hypothesis_en, it: m.hypothesis_it })
  const commentary = pickText(lang, { it: m.commentary?.it, en: m.commentary?.en })
  const facts = [
    t('matches.wdl', { w: f.num(m.wins), d: f.num(m.draws), l: f.num(m.losses) }),
    m.elo === null ? '' : `${f.signed(m.elo)}${m.elo_error === null ? '' : ` ± ${f.num(Math.round(m.elo_error))}`} Elo`,
    m.time_control,
    m.finished_at ? f.dateTime(m.finished_at) : '',
  ].filter(Boolean)
  return (
    <li className="grid gap-1.5 py-3 first:pt-0 last:pb-0">
      <p className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <b className="text-[14px] font-semibold">{title(i18n, m)}</b>
        {verdict && (
          <span className={cn('rounded-full px-2 py-px text-[12px] font-semibold', verdict.tone)}>{t(verdict.key)}</span>
        )}
      </p>
      <p className="text-[12px] text-muted-foreground tabular-nums">{facts.join(' · ')}</p>
      {hypothesis && (
        <ClampText text={plainText(hypothesis.text)} lang={hypothesis.lang} badge={hypothesis.fallback} lines={2}
                   className="text-[13px] leading-snug" />
      )}
      {commentary && (
        <ClampText text={commentary.text} lang={commentary.lang} badge={commentary.fallback}
                   className="text-[13px] leading-relaxed text-muted-foreground" />
      )}
    </li>
  )
}

/** "Candidato #12 contro il campione", "Candidate #12 vs the random player". */
function title(i18n: I18n, m: JudgedMatch): string {
  const { t } = i18n
  if (m.opponent === 'random') return t('matches.vsRandom', { id: m.experiment_id })
  if (m.opponent === 'champion') return t('matches.vsChampion', { id: m.experiment_id })
  const gen = /^gen-(\d+)$/.exec(m.opponent)
  if (gen) return t('matches.vsGeneration', { id: m.experiment_id, gen: gen[1] ?? '' })
  return t('matches.vsOther', { id: m.experiment_id, opponent: m.opponent })
}
