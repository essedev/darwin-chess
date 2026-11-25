import { ExternalLink } from 'lucide-react'
import { useState } from 'react'
import type { AgentEvent, Lichess, LiveGame, Overview } from '@/lib/api'
import { cn } from '@/lib/utils'
import { ArenaGame } from './arena-game'
import { TOOLS, matchLabel, plainText } from './format'
import { LichessPanel } from './lichess-game'

type Ready = Extract<Overview, { ready: true }>
type Tab = 'arena' | 'lichess'
type LichessQuery = { isPending: boolean; isError: boolean; data: Lichess | undefined }

export function Stage(props: { data: Ready; game: LiveGame | null; events: AgentEvent[]; lichess: LichessQuery }) {
  const { data, game, lichess } = props
  const [tab, setTab] = useState<Tab>(() => (window.location.hash === '#lichess' ? 'lichess' : 'arena'))
  const choose = (next: Tab) => {
    setTab(next)
    // The Lichess tab has its own address, so a link can open the dashboard on it.
    window.history.replaceState(null, '', next === 'lichess' ? '#lichess' : window.location.pathname)
  }
  const live = lichess.data?.live ?? null
  const label = game ? matchLabel(game.white, game.black, data.current?.id, data.champion.id) : null
  return (
    <div className="order-1 grid min-w-0 content-start justify-items-center gap-[18px] lg:order-none">
      <div className="grid w-full min-w-0 max-w-[640px] gap-3 lg:max-w-[min(100%,calc(100vh-264px))]">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <Tabs tab={tab} onChange={choose} lichessLive={live !== null} />
          {tab === 'arena' && label && <MatchLabel {...label} />}
          {tab === 'lichess' && live && (
            <a href={live.url} target="_blank" rel="noreferrer"
               className="ml-auto inline-flex cursor-pointer items-center gap-1.5 text-[13px] font-medium text-live hover:underline">
              Apri su Lichess <ExternalLink className="size-4" aria-hidden />
            </a>
          )}
        </div>
        <div id={`stage-${tab}`} role="tabpanel" aria-labelledby={`tab-${tab}`} className="min-w-0">
          {tab === 'arena' ? <ArenaGame data={data} game={game} /> : <LichessPanel query={lichess} />}
        </div>
      </div>
      <Caption events={props.events} agent={data.agent} />
    </div>
  )
}

const TABS: { key: Tab; name: string }[] = [
  { key: 'arena', name: 'Arbitro' },
  { key: 'lichess', name: 'Lichess' },
]

function Tabs({ tab, onChange, lichessLive }: { tab: Tab; onChange: (tab: Tab) => void; lichessLive: boolean }) {
  return (
    <div role="tablist" aria-label="Partita mostrata" className="inline-flex rounded-full bg-muted p-[3px]">
      {TABS.map((t) => (
        <button key={t.key} id={`tab-${t.key}`} type="button" role="tab" aria-selected={tab === t.key}
                aria-controls={`stage-${t.key}`} onClick={() => onChange(t.key)}
                className={cn(
                  'inline-flex h-7 cursor-pointer items-center gap-1.5 rounded-full px-3.5 text-[13px] font-medium transition-colors',
                  tab === t.key ? 'bg-card text-foreground shadow-[0_1px_2px_rgb(0_0_0/0.12)]' : 'text-muted-foreground hover:text-foreground',
                )}>
          {t.name}
          {t.key === 'lichess' && lichessLive && (
            <>
              <i className="size-1.5 animate-pulse rounded-full bg-bad" aria-hidden />
              <span className="sr-only">, partita in corso</span>
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

function Caption({ events, agent }: { events: AgentEvent[]; agent: Ready['agent'] }) {
  const thought = [...events].reverse().find((e) => e.kind === 'thought')
  const action = [...events].reverse().find((e) => e.kind === 'tool_call')
  const label = agent === 'paused' ? 'Agente in pausa' : agent === 'working' ? 'L’agente pensa' : 'Ultimo pensiero'
  const tool = action ? String(action.payload.tool) : ''
  const text = thought ? plainText(String(thought.payload.text)) : ''
  return (
    <div className="w-full max-w-[680px] text-center">
      <p className="mb-2 inline-flex items-center gap-1.5 font-mono text-[11px] font-medium tracking-wider text-muted-foreground uppercase">
        <i className="size-1.5 rounded-full bg-live" /> {label}
      </p>
      <p className="line-clamp-3 text-[17px] leading-snug font-medium text-balance lg:text-xl" title={text}>
        {text || 'Ancora nessun pensiero da mostrare.'}
      </p>
      {action && (
        <p className="mt-2.5 font-mono text-xs text-muted-foreground">
          {TOOLS[tool] ?? tool} · {new Date(action.at).toLocaleTimeString('it-IT', { hour: '2-digit', minute: '2-digit' })}
        </p>
      )}
    </div>
  )
}
