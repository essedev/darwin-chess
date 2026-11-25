import { ErrorNote, LoadingNote, StateNote, card } from '@/components/page'
import { plainText } from '@/features/live/format'
import { pickText, useI18n } from '@/i18n/context'
import { LangBadge, Rich } from '@/i18n/parts'
import { type GenerationDetail, useGenerationsDetail } from '@/lib/api'
import { href } from '@/lib/use-route'
import { cn } from '@/lib/utils'

export function GenerationTimeline() {
  const { t } = useI18n()
  const generations = useGenerationsDetail()
  return (
    <section aria-labelledby="generations" className="grid min-w-0 gap-4">
      <h2 id="generations" className="text-[19px] font-semibold tracking-tight">{t('generations.title')}</h2>
      {generations.isPending ? (
        <LoadingNote what={t('what.generations')} />
      ) : generations.isError ? (
        <ErrorNote what={t('what.generations')} onRetry={() => void generations.refetch()} />
      ) : generations.data.length === 0 ? (
        <StateNote title={t('generations.none.title')} text={t('generations.none.text')} className={card} />
      ) : (
        <ol className="grid">
          {generations.data.map((g, i) => (
            <GenerationItem key={g.id} generation={g} champion={i === 0} last={i === generations.data.length - 1} />
          ))}
        </ol>
      )}
    </section>
  )
}

function GenerationItem({ generation: g, champion, last }: { generation: GenerationDetail; champion: boolean; last: boolean }) {
  const { t, lang, f } = useI18n()
  const seed = g.id === 0
  const hypothesis = seed ? null : pickText(lang, { en: g.hypothesis, it: g.hypothesis_it })
  const lesson = pickText(lang, { en: g.lesson, it: g.lesson_it })
  const headline = seed ? t('generations.seed') : hypothesis ? plainText(hypothesis.text) : t('experiment.noHypothesis')
  return (
    <li className="relative grid grid-cols-[20px_minmax(0,1fr)] gap-x-3">
      <span aria-hidden className="relative flex justify-center">
        {!last && <i className="absolute top-3 bottom-0 w-px bg-border" />}
        <i className={cn('relative mt-[7px] size-2.5 rounded-full ring-4 ring-background', champion ? 'bg-live' : 'bg-muted-foreground/50')} />
      </span>
      <article className="grid min-w-0 gap-2 pb-7">
        <p className="flex flex-wrap items-baseline gap-x-2.5 gap-y-0.5 text-[12px] text-muted-foreground">
          <span className={cn('font-mono text-[13px] font-medium', champion ? 'text-live' : 'text-foreground')}>gen-{g.id}</span>
          {champion && <span className="font-medium text-live">{t('generations.champion')}</span>}
          <time dateTime={g.created_at}>{f.dateTime(g.created_at)}</time>
        </p>
        <h3 className="text-[16px] leading-snug font-semibold text-pretty" lang={hypothesis?.lang}>
          {hypothesis?.fallback && <LangBadge lang={hypothesis.lang} className="mr-1.5" />}
          {headline}
        </h3>
        {!seed && <Facts generation={g} />}
        {lesson && (
          <p className="text-[13px] leading-relaxed text-muted-foreground">
            <span className="font-medium text-foreground">{t('generations.lesson')} </span>
            {lesson.fallback && <LangBadge lang={lesson.lang} className="mr-1.5" />}
            <span lang={lesson.lang}>{plainText(lesson.text)}</span>
          </p>
        )}
        <a
          href={seed ? href('codice', { ref: 'gen-0' }) : href('codice', { diff: `gen-${g.id}` })}
          className="w-fit cursor-pointer text-[13px] font-medium text-live underline-offset-4 hover:underline"
        >
          {seed ? t('generations.browseSeed') : t('generations.whatChanged')}
        </a>
      </article>
    </li>
  )
}

function Facts({ generation: g }: { generation: GenerationDetail }) {
  const { t, tn, f } = useI18n()
  const facts: { text: string; tone?: string }[] = []
  if (g.id === 1) facts.push({ text: t('generations.beatsRandom'), tone: 'text-good' })
  else if (g.elo_vs_parent !== null) facts.push({ text: t('generations.gain', { elo: f.signed(g.elo_vs_parent) }), tone: 'text-good' })
  if (g.below_ladder) facts.push({ text: t('generations.belowLadder') })
  else if (g.elo_absolute !== null) facts.push({ text: t('generations.about', { elo: f.num(Math.round(g.elo_absolute)) }) })
  facts.push({ text: g.tried <= 1 ? t('generations.firstTry') : t('generations.afterTries', { n: g.tried }) })
  if (g.diff_stat) {
    const { files, insertions, deletions } = g.diff_stat
    facts.push({ text: t('generations.diff', { files: tn('count.files', files), plus: f.num(insertions), minus: f.num(deletions) }) })
  }
  const l = g.lichess
  return (
    <div className="grid gap-1.5">
      <p className="flex flex-wrap gap-x-3 gap-y-1 text-[13px]">
        {facts.map((fact) => (
          <span key={fact.text} className={cn('font-medium', fact.tone ?? 'text-muted-foreground')}>{fact.text}</span>
        ))}
      </p>
      {l && l.games > 0 && (
        <p className="text-[13px] text-muted-foreground">
          <Rich
            text={t('generations.lichess')}
            values={{
              performance: <span className="font-mono font-medium text-foreground tabular-nums">{f.num(l.performance)}</span>,
              games: tn('count.games', l.games),
              wdl: t('matches.wdl', { w: l.wins, d: l.draws, l: l.losses }),
            }}
          />
        </p>
      )}
    </div>
  )
}
