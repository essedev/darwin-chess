import { ExternalLink } from 'lucide-react'
import { useState } from 'react'
import { type I18n, useI18n } from '@/i18n/context'
import type { AgentEvent, Lichess, LiveGame, Overview } from '@/lib/api'
import { cn } from '@/lib/utils'
import { ArenaGame } from './arena-game'
import { matchLabel, plainText } from './format'
import { JudgedMatches } from './judged-matches'
import { LichessPanel } from './lichess-game'
import { RecentGames } from './lichess-recent'

type Ready = Extract<Overview, { ready: true }>
type Tab = 'arena' | 'lichess'
type LichessQuery = { isPending: boolean; isError: boolean; data: Lichess | undefined }

/**
 * The board, the agent's last thought under it, then the list that belongs to the tab: the
 * judged matches or the Lichess games. The list sits below everything else, so when it grows
 * or shrinks the board above does not move.
 */
export function Stage(props: { data: Ready; game: LiveGame | null; events: AgentEvent[]; lichess: LichessQuery }) {
  const { data, game, lichess } = props
  const i18n = useI18n()
  const [tab, setTab] = useState<Tab>(() => (window.location.hash === '#lichess' ? 'lichess' : 'arena'))
  const choose = (next: Tab) => {
    setTab(next)
    // The Lichess tab has its own address, so a link can open the dashboard on it.
    window.history.replaceState(null, '', next === 'lichess' ? '#lichess' : window.location.pathname)
  }
  const live = lichess.data?.live ?? null
  const label = game ? matchLabel(i18n, game.white, game.black, data.current?.id, data.champion.id) : null
  return (
    <div className="order-1 grid min-w-0 content-start justify-items-center gap-[18px] lg:order-none">
      <div className="grid w-full min-w-0 max-w-[640px] gap-3 lg:max-w-[min(100%,calc(100vh-264px))]">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <Tabs tab={tab} onChange={choose} lichessLive={live !== null} />
          {tab === 'arena' && label && <MatchLabel {...label} />}
          {tab === 'lichess' && live && (
            <a href={live.url} target="_blank" rel="noreferrer"
               className="ml-auto inline-flex cursor-pointer items-center gap-1.5 text-[13px] font-medium text-live hover:underline">
              {i18n.t('lichess.open')} <ExternalLink className="size-4" aria-hidden />
            </a>
          )}
        </div>
        <div id={`stage-${tab}`} role="tabpanel" aria-labelledby={`tab-${tab}`} className="min-w-0">
          {tab === 'arena' ? <ArenaGame data={data} game={game} /> : <LichessPanel query={lichess} />}
        </div>
      </div>
      <Caption events={props.events} agent={data.agent} />
      <div className="w-full min-w-0 max-w-[680px]">
        {tab === 'arena' ? <JudgedMatches /> : <RecentGames query={lichess} />}
      </div>
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

/** "Giudizio · candidato #6 contro il campione gen-2": the kind of game, then who plays. */
function MatchLabel({ kind, players }: { kind: string; players: string }) {
  return (
    <p className="min-w-0 text-[13px] text-muted-foreground">
      <b className="font-semibold text-foreground">{kind}</b> · {players}
    </p>
  )
}

/** The agent's last thought, always in English: the language it works in. */
function Caption({ events, agent }: { events: AgentEvent[]; agent: Ready['agent'] }) {
  const i18n = useI18n()
  const { t, label: labelOf, lang, f } = i18n
  const thought = [...events].reverse().find((e) => e.kind === 'thought')
  const action = [...events].reverse().find((e) => e.kind === 'tool_call')
  const label = captionLabel(i18n, agent)
  const tool = action ? String(action.payload.tool) : ''
  const text = thought ? plainText(String(thought.payload.text)) : ''
  return (
    <div className="w-full max-w-[680px] text-center">
      <p className="mb-2 inline-flex items-center gap-1.5 font-mono text-[11px] font-medium tracking-wider text-muted-foreground uppercase">
        <i className="size-1.5 rounded-full bg-live" /> {label}
      </p>
      {text ? (
        <p lang="en" className="line-clamp-3 text-[17px] leading-snug font-medium text-balance lg:text-xl" title={text}>
          {text}
        </p>
      ) : (
        <p className="text-[17px] leading-snug font-medium text-balance lg:text-xl">{t('caption.empty')}</p>
      )}
      {action && (
        <p className="mt-2.5 font-mono text-xs text-muted-foreground">
          {labelOf('tool', tool)} · {f.time(action.at)}
        </p>
      )}
      {text && lang === 'it' && <p className="mt-1.5 text-[12px] text-muted-foreground">{t('caption.english')}</p>}
    </div>
  )
}

function captionLabel({ t }: I18n, agent: Ready['agent']) {
  if (agent === 'paused') return t('agent.paused')
  return agent === 'working' ? t('caption.thinking') : t('caption.last')
}
