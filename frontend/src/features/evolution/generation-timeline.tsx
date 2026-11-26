import { ExpandRow, Fact } from '@/components/expand-row'
import { ErrorNote, LoadingNote, StateNote } from '@/components/page'
import { Help, panel } from '@/components/panel'
import { hueStyle } from '@/lib/hue'
import { EloChart } from '@/features/live/elo-chart'
import { type EloPoint, MIN_PERFORMANCE_GAMES, plainText, titleText } from '@/features/live/format'
import { pickText, useI18n } from '@/i18n/context'
import { LangBadge } from '@/i18n/parts'
import { type GenerationDetail, useGenerationsDetail } from '@/lib/api'
import { href } from '@/lib/use-route'
import { cn } from '@/lib/utils'

/** Every champion, newest first: the Elo chart with its margins, then one row each. */
export function GenerationTimeline() {
  const { t } = useI18n()
  const generations = useGenerationsDetail()
  const rated: EloPoint[] = (generations.data ?? [])
    .filter((g) => g.elo_absolute !== null && g.elo_absolute_error != null)
    .map((g) => ({ id: g.id, elo: g.elo_absolute ?? 0, error: g.elo_absolute_error ?? 0 }))
    .reverse()
  return (
    <section aria-labelledby="generations" className="grid min-w-0 content-start gap-4">
      <h2 id="generations" className="text-[19px] font-semibold tracking-tight">{t('generations.title')}</h2>
      {generations.isPending ? (
        <LoadingNote what={t('what.generations')} />
      ) : generations.isError ? (
        <ErrorNote what={t('what.generations')} onRetry={() => void generations.refetch()} />
      ) : generations.data.length === 0 ? (
        <StateNote art="empty" title={t('generations.none.title')} text={t('generations.none.text')} className={cn(panel, 'p-5')} />
      ) : (
        <>
          {rated.length > 0 && (
            <div className={cn(panel, 'p-5')} style={hueStyle('strength')}>
              <p className="panel-label mb-3 flex items-center gap-1.5">
                {t('elo.chartTitle')} <Help text={t('elo.help')} />
              </p>
              <EloChart points={rated} height={170} axis />
            </div>
          )}
          <ol className="grid gap-0.5">
            {generations.data.map((g, i) => (
              <GenerationRow key={g.id} generation={g} champion={i === 0} />
            ))}
          </ol>
        </>
      )}
    </section>
  )
}

function GenerationRow({ generation: g, champion }: { generation: GenerationDetail; champion: boolean }) {
  const { t, lang, f } = useI18n()
  const columns = 'grid-cols-[52px_minmax(0,1fr)_auto_16px]'
  if (g.id === 0) {
    return (
      <ExpandRow
        columns="grid-cols-[52px_minmax(0,1fr)_auto]"
        line={
          <>
            <span className="font-mono text-[13px] font-medium text-muted-foreground">gen-0</span>
            <span className="min-w-0">
              <b className="block text-[14px] font-semibold">{t('generations.seed')}</b>
              <span className="block text-[12px] text-muted-foreground">{f.dateTime(g.created_at)}</span>
            </span>
            <a href={href('codice', { ref: 'gen-0' })} className="cursor-pointer text-[12px] font-medium text-live underline-offset-4 hover:underline">
              {t('generations.browseSeed')}
            </a>
          </>
        }
      />
    )
  }
  const title = titleText(lang, g.title, { en: g.hypothesis, it: g.hypothesis_it })
  return (
    <ExpandRow
      columns={columns}
      line={
        <>
          <span className={cn('font-mono text-[13px] font-medium', champion && 'text-live')}>gen-{g.id}</span>
          <span className="min-w-0">
            <b className="block truncate text-[14px] font-semibold" lang={title?.lang}>{title?.text ?? t('experiment.noHypothesis')}</b>
            <span className="block truncate text-[12px] text-muted-foreground">
              {champion && <span className="font-medium text-live">{t('generations.champion')} · </span>}
              {g.tried <= 1 ? t('generations.firstTry') : t('generations.afterTries', { n: g.tried })} · {f.time(g.created_at)}
            </span>
          </span>
          <span className="text-right font-mono text-[14px] font-medium text-c-strength tabular-nums">
            {g.elo_absolute !== null ? (
              <>
                {f.num(Math.round(g.elo_absolute))}
                {g.elo_absolute_error != null && (
                  <small className="block text-[11px] font-normal text-muted-foreground">± {f.num(Math.round(g.elo_absolute_error))}</small>
                )}
              </>
            ) : (
              <span className="font-sans text-[12px] font-normal text-muted-foreground">
                {g.below_ladder ? t('generations.belowLadderShort') : t('generations.notRated')}
              </span>
            )}
          </span>
        </>
      }
    >
      <GenerationDetails generation={g} />
    </ExpandRow>
  )
}

function GenerationDetails({ generation: g }: { generation: GenerationDetail }) {
  const { t, tn, lang, f } = useI18n()
  const hypothesis = pickText(lang, { en: g.hypothesis, it: g.hypothesis_it })
  const note = pickText(lang, { en: g.lesson, it: g.lesson_it })
  const l = g.lichess
  const gain = g.elo_vs_parent === null
    ? null
    : `${f.signed(g.elo_vs_parent)}${g.elo_vs_parent_error == null ? '' : ` ± ${f.num(Math.round(g.elo_vs_parent_error))}`}`
  return (
    <>
      {hypothesis && (
        <p>
          <b className="block font-semibold">{t('detail.hypothesis')}</b>
          {hypothesis.fallback && <LangBadge lang={hypothesis.lang} className="mr-1.5" />}
          <span lang={hypothesis.lang}>{plainText(hypothesis.text)}</span>
        </p>
      )}
      <p className="flex flex-wrap gap-x-4 gap-y-1">
        <Fact label={t('detail.elo')}>
          {g.elo_absolute !== null
            ? `${f.num(Math.round(g.elo_absolute))}${g.elo_absolute_error == null ? '' : ` ± ${f.num(Math.round(g.elo_absolute_error))}`}`
            : g.below_ladder ? t('generations.belowLadder') : t('generations.notRated')}
        </Fact>
        {g.elo_anchors != null && (
          <Fact label={t('detail.stockfish')}>
            {`${f.num(Math.round(g.elo_anchors))}${g.elo_anchors_error == null ? '' : ` ± ${f.num(Math.round(g.elo_anchors_error))}`}`}
          </Fact>
        )}
        {gain && (
          <span className="inline-flex items-center gap-1.5">
            <Fact label={g.id === 1 ? t('detail.vsRandom') : t('detail.vsParent')}>{gain}</Fact>
            <Help text={t('detail.gainHelp')} />
          </span>
        )}
        {g.diff_stat && (
          <Fact label={t('detail.code')}>
            {tn('count.files', g.diff_stat.files)} · +{f.num(g.diff_stat.insertions)} −{f.num(g.diff_stat.deletions)}
          </Fact>
        )}
      </p>
      {l && l.games > 0 && (
        <p className="text-muted-foreground">
          {l.games >= MIN_PERFORMANCE_GAMES
            ? t('detail.lichess', {
                performance: f.num(l.performance),
                games: tn('count.games', l.games),
                wdl: t('matches.wdl', { w: l.wins, d: l.draws, l: l.losses }),
              })
            : t('elo.lichessFew', { games: tn('count.games', l.games) })}
        </p>
      )}
      {note && (
        <p>
          <b className="block font-semibold">{t('detail.note')}</b>
          {note.fallback && <LangBadge lang={note.lang} className="mr-1.5" />}
          <span lang={note.lang} className="text-muted-foreground">{plainText(note.text)}</span>
        </p>
      )}
      <a href={href('codice', { diff: `gen-${g.id}` })} className="w-fit cursor-pointer font-medium text-live underline-offset-4 hover:underline">
        {t('generations.whatChanged')}
      </a>
    </>
  )
}
