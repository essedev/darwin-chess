import { ExternalLink } from 'lucide-react'
import { type I18n, useI18n } from '@/i18n/context'
import type { AgentEvent, Lichess, LiveGame, Overview } from '@/lib/api'
import { cn } from '@/lib/utils'
import { AgentLine } from '@/features/session/agent-line'
import { WorkCard } from '@/features/session/work-card'
import { ArenaGame } from './arena-game'
import { matchLabel, plainText, titleText } from './format'
import { LichessPanel } from './lichess-game'

type Ready = Extract<Overview, { ready: true }>
export type Tab = 'arena' | 'lichess'
type LichessQuery = { isPending: boolean; isError: boolean; data: Lichess | undefined }

/**
 * The middle column: which game, what it is about, the board, what the agent is doing. With
 * no referee game the arena shows the agent's session instead of an empty board.
 */
export function Stage(props: {
  data: Ready
  game: LiveGame | null
  events: AgentEvent[]
  lichess: LichessQuery
  tab: Tab
  onTab: (tab: Tab) => void
}) {
  const { data, game, lichess, tab } = props
  const { t } = useI18n()
  const live = lichess.data?.live ?? null
  const running = data.current?.status === 'running' ? data.current : null
  const work = tab === 'arena' && !game && !data.on_trial ? data.current : null
  return (
    <div className="order-1 grid min-w-0 content-start gap-3.5 xl:order-none">
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
        <Tabs tab={tab} onChange={props.onTab} lichessLive={live !== null} />
        {tab === 'lichess' && live && (
          <a href={live.url} target="_blank" rel="noreferrer"
             className="inline-flex cursor-pointer items-center gap-1.5 text-[13px] font-medium text-live hover:underline">
            {t('lichess.open')} <ExternalLink className="size-4" aria-hidden />
          </a>
        )}
      </div>
      {tab === 'arena' ? <ArenaHeading data={data} game={game} /> : live && (
        <Heading tag="Lichess" title={t('lichess.heading', { opponent: live.opponent.name })}
                 detail={`gen-${live.generation} · ${live.time_control}`} />
      )}
      <div id={`stage-${tab}`} role="tabpanel" aria-labelledby={`tab-${tab}`} className="min-w-0">
        {work ? (
          <WorkCard experimentId={work.id} running={running !== null} streamed={props.events} />
        ) : tab === 'arena' ? (
          <ArenaGame data={data} game={game} />
        ) : (
          <LichessPanel query={lichess} />
        )}
      </div>
      {work ? null : running ? (
        <AgentLine experimentId={running.id} events={props.events} />
      ) : (
        <Caption events={props.events} agent={data.agent} />
      )}
    </div>
  )
}

/** "#18 Doubled pawn penalty, against champion gen-5", or what else is on the board. */
function ArenaHeading({ data, game }: { data: Ready; game: LiveGame | null }) {
  const i18n = useI18n()
  const { t, lang } = i18n
  const current = data.on_trial ?? data.current
  // Between two games of a trial the board is empty, but the trial is still what is on.
  if (!game) {
    if (!data.on_trial) return null
    const title = titleText(lang, data.on_trial.title, { en: data.on_trial.hypothesis, it: data.on_trial.hypothesis_it })
    return <Heading tag={`#${data.on_trial.id}`} title={title?.text ?? t('player.candidate', { id: data.on_trial.id })} lang={title?.lang} />
  }
  const label = matchLabel(i18n, game.white, game.black, current?.id, data.champion.id)
  const engines = [game.white, game.black]
  if (current && engines.includes('candidate')) {
    const title = titleText(lang, current.title, { en: current.hypothesis, it: current.hypothesis_it })
    const opponent = engines.includes('random') ? t('stage.vsRandom') : t('stage.vsChampion', { gen: data.champion.id })
    return <Heading tag={`#${current.id}`} title={title?.text ?? t('player.candidate', { id: current.id })}
                    lang={title?.lang} detail={opponent} />
  }
  return label ? <Heading tag={label.kind} title={label.players} /> : <Heading title={`${game.white} – ${game.black}`} />
}

function Heading({ tag, title, detail, lang }: { tag?: string; title: string; detail?: string; lang?: string }) {
  return (
    <div className="flex min-w-0 flex-wrap items-baseline gap-x-2.5 gap-y-0.5">
      {tag && <span className="font-mono text-[13px] font-medium text-live">{tag}</span>}
      <h2 className="line-clamp-2 min-w-0 text-[21px] leading-tight font-semibold tracking-tight text-balance" lang={lang} title={title}>{title}</h2>
      {detail && <p className="text-[13px] text-muted-foreground">{detail}</p>}
    </div>
  )
}

const TABS: Tab[] = ['arena', 'lichess']

function Tabs({ tab, onChange, lichessLive }: { tab: Tab; onChange: (tab: Tab) => void; lichessLive: boolean }) {
  const { t } = useI18n()
  return (
    <div role="tablist" aria-label={t('stage.tablist')} className="inline-flex rounded-full bg-muted p-[3px]">
      {TABS.map((key) => (
        <button key={key} id={`tab-${key}`} type="button" role="tab" aria-selected={tab === key}
                aria-controls={`stage-${key}`} onClick={() => onChange(key)}
                className={cn(
                  'inline-flex h-7 cursor-pointer items-center gap-1.5 rounded-full px-3.5 text-[13px] font-medium transition-colors',
                  tab === key ? 'bg-card text-foreground shadow-[0_1px_2px_rgb(0_0_0/0.12)]' : 'text-muted-foreground hover:text-foreground',
                )}>
          {t(`stage.tab.${key}`)}
          {key === 'lichess' && lichessLive && (
            <>
              <i className="size-1.5 animate-pulse rounded-full bg-bad" aria-hidden />
              <span className="sr-only">{t('stage.liveGame')}</span>
            </>
          )}
        </button>
      ))}
    </div>
  )
}

/** The agent's last thought, in English (the language it works in), cut to two lines. */
function Caption({ events, agent }: { events: AgentEvent[]; agent: Ready['agent'] }) {
  const i18n = useI18n()
  const { t, f, lang } = i18n
  const thought = [...events].reverse().find((e) => e.kind === 'thought')
  const italian = lang === 'it' && thought?.text_it ? plainText(thought.text_it) : ''
  const text = italian || (thought ? plainText(String(thought.payload.text)) : '')
  return (
    <div className="mx-auto mt-1 w-full max-w-[620px] text-center">
      <p className="font-mono text-[11px] font-medium tracking-wider text-c-gens uppercase">
        {captionLabel(i18n, agent)}
        {text && lang === 'it' && !italian && `, ${t('caption.inEnglish')}`}
        {thought && ` · ${f.time(thought.at)}`}
      </p>
      <p lang={italian ? 'it' : text ? 'en' : undefined} title={text || undefined}
         className="mt-1.5 line-clamp-2 text-[17px] leading-snug font-medium text-balance lg:text-lg">
        {text || t('caption.empty')}
      </p>
    </div>
  )
}

function captionLabel({ t }: I18n, agent: Ready['agent']) {
  if (agent === 'paused') return t('agent.paused')
  return agent === 'working' ? t('caption.thinking') : t('caption.last')
}
