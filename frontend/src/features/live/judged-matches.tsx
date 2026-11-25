import { Panel, PanelFooter } from '@/components/panel'
import { ErrorNote, LoadingNote } from '@/components/page'
import { pickText, useI18n } from '@/i18n/context'
import { isClientError, type JudgedMatch } from '@/lib/api'
import { href } from '@/lib/use-route'
import { cn } from '@/lib/utils'
import { titleText } from './format'

/** The live page shows a fixed three: the column never grows, the history is in Evoluzione. */
export const RECENT_SHOWN = 3

const VERDICT: Record<string, { key: 'matches.verdict.h1' | 'matches.verdict.h0' | 'matches.verdict.continue'; tone: string }> = {
  h1: { key: 'matches.verdict.h1', tone: 'bg-good/12 text-good' },
  h0: { key: 'matches.verdict.h0', tone: 'bg-bad/12 text-bad' },
  continue: { key: 'matches.verdict.continue', tone: 'bg-muted text-muted-foreground' },
}

type Query = { isPending: boolean; isError: boolean; error: Error | null; data: JudgedMatch[] | undefined }

/** The referee's last three verdicts, with a link to all of them. */
export function JudgedMatches({ query: matches }: { query: Query }) {
  const { t } = useI18n()
  // An API without the endpoint yet answers 404: the section simply is not there.
  if (matches.isError && matches.error && isClientError(matches.error)) return null
  return (
    <Panel title={t('matches.title')}>
      {matches.isPending ? (
        <LoadingNote what={t('what.matches')} className="py-3" />
      ) : matches.isError && !matches.data ? (
        <ErrorNote what={t('what.matches')} className="py-3" />
      ) : !matches.data?.length ? (
        <p className="text-[13px]">{t('matches.none')}</p>
      ) : (
        <ol className="grid divide-y">
          {matches.data.slice(0, RECENT_SHOWN).map((match) => (
            <Row key={match.id} match={match} />
          ))}
        </ol>
      )}
      {matches.isError && matches.data && <p className="mt-2 text-[12px] text-muted-foreground">{t('list.stale')}</p>}
      <PanelFooter>
        <span />
        <a href={href('evoluzione')} className="cursor-pointer font-medium text-live underline-offset-4 hover:underline">
          {t('matches.all')}
        </a>
      </PanelFooter>
    </Panel>
  )
}

function Row({ match: m }: { match: JudgedMatch }) {
  const { t, tn, lang, f } = useI18n()
  const verdict = m.verdict ? VERDICT[m.verdict] : undefined
  const title = titleText(lang, m.title, { en: m.hypothesis_en, it: m.hypothesis_it })
  const commentary = pickText(lang, { it: m.commentary?.it, en: m.commentary?.en })
  const facts = [
    tn('count.games', m.wins + m.draws + m.losses),
    m.elo === null ? '' : `${f.signed(m.elo)}${m.elo_error === null ? '' : ` ± ${f.num(Math.round(m.elo_error))}`} ${t(m.opponent === 'random' ? 'matches.vsRandomShort' : 'matches.vsChampionShort')}`,
    m.finished_at ? f.time(m.finished_at) : '',
  ].filter(Boolean)
  return (
    <li className="grid gap-1 py-3 first:pt-0 last:pb-0">
      <p className="flex min-w-0 items-baseline gap-2.5">
        <span className="flex-none font-mono text-[12px] font-medium text-muted-foreground">#{m.experiment_id}</span>
        <b className="min-w-0 truncate text-[14px] font-semibold" lang={title?.lang} title={title?.text}>{title?.text}</b>
        {verdict && (
          <span className={cn('ml-auto flex-none rounded-full px-2 py-px text-[12px] font-semibold', verdict.tone)}>{t(verdict.key)}</span>
        )}
      </p>
      <p className="text-[12px] text-muted-foreground tabular-nums">{facts.join(' · ')}</p>
      {commentary && (
        <p className="line-clamp-2 text-[13px] leading-normal text-muted-foreground" lang={commentary.lang} title={commentary.text}>
          {commentary.text}
        </p>
      )}
    </li>
  )
}
