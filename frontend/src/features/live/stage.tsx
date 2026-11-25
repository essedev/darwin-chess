import { useEffect, useRef } from 'react'
import type { AgentEvent, LiveGame, Overview } from '@/lib/api'
import { Board } from './board'
import { TOOLS } from './format'

type Ready = Extract<Overview, { ready: true }>

const START = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1'

const NAMES: Record<string, (data: Ready) => string> = {
  candidate: (d) => `Candidato #${d.current?.id ?? ''}`,
  champion: (d) => `Campione gen-${d.champion.id}`,
  random: () => 'Giocatore casuale',
}

export function Stage({ data, game, events }: { data: Ready; game: LiveGame | null; events: AgentEvent[] }) {
  const name = (engine: string) => (NAMES[engine] ? NAMES[engine](data) : engine)
  const score = (engine: string) => game?.tally[engine]?.wins ?? 0
  return (
    <div className="order-1 grid min-w-0 content-start justify-items-center gap-[18px] lg:order-none">
      <div className="grid w-full min-w-0 max-w-[640px] grid-cols-1 gap-x-4 gap-y-2.5 lg:max-w-[min(100%,calc(100vh-224px))] lg:grid-cols-[minmax(0,1fr)_130px]">
        <Player colour="black" label={game ? name(game.black) : 'In attesa di una partita'} detail={game ? 'nero' : ''} points={game ? score(game.black) : null} />
        <span className="hidden lg:block" />
        <div className="min-w-0">
          <Board fen={game?.fen ?? START} lastMove={game?.last_move ?? null} />
        </div>
        <Moves game={game} />
        <Player colour="white" label={game ? name(game.white) : ''} detail={game ? 'bianco' : ''} points={game ? score(game.white) : null} />
      </div>
      <Caption events={events} agent={data.agent} />
    </div>
  )
}

function Player(props: { colour: 'white' | 'black'; label: string; detail: string; points: number | null }) {
  return (
    <div className="flex min-h-10 items-center gap-3 px-0.5">
      <span className={`size-3 flex-none rounded-full shadow-[0_0_0_1.5px_var(--border)] ${props.colour === 'white' ? 'bg-[#fbfaf7]' : 'bg-[#16140f]'}`} />
      <span className="min-w-0">
        <b className="block truncate text-[15px] font-semibold">{props.label}</b>
        <span className="block text-xs text-muted-foreground">{props.detail}</span>
      </span>
      {props.points !== null && (
        <span className="ml-auto text-right">
          <b className="block font-mono text-xl leading-none font-medium tabular-nums">{props.points}</b>
          <span className="text-xs text-muted-foreground">vinte</span>
        </span>
      )}
    </div>
  )
}

function Moves({ game }: { game: LiveGame | null }) {
  const box = useRef<HTMLDivElement>(null)
  const san = game?.san ?? []
  useEffect(() => {
    box.current?.scrollTo({ top: box.current.scrollHeight, left: box.current.scrollWidth })
  }, [san.length])
  const firstBlack = (game?.start_ply ?? 0) % 2 === 1
  const plies = firstBlack ? ['…', ...san] : san
  const rows = []
  for (let i = 0; i < plies.length; i += 2) rows.push([plies[i], plies[i + 1]])
  const firstMove = Math.floor((game?.start_ply ?? 0) / 2) + 1
  return (
    <div ref={box} className="flex min-w-0 gap-0.5 overflow-x-auto font-mono text-xs tabular-nums [scrollbar-width:none] lg:block lg:max-h-[calc(100vh-300px)] lg:overflow-y-auto lg:py-5">
      {rows.length === 0 && <span className="text-muted-foreground">nessuna mossa</span>}
      {rows.map(([white, black], i) => (
        <div key={i} className="grid h-[26px] flex-none grid-cols-[26px_1fr_1fr] items-center">
          <span className="text-[11px] text-muted-foreground">{firstMove + i}</span>
          <span className={`rounded-md px-1.5 py-1 ${i === rows.length - 1 && !black ? 'bg-live/22 font-medium' : ''}`}>{white}</span>
          <span className={`rounded-md px-1.5 py-1 ${i === rows.length - 1 && black ? 'bg-live/22 font-medium' : ''}`}>{black ?? ''}</span>
        </div>
      ))}
    </div>
  )
}

function Caption({ events, agent }: { events: AgentEvent[]; agent: Ready['agent'] }) {
  const thought = [...events].reverse().find((e) => e.kind === 'thought')
  const action = [...events].reverse().find((e) => e.kind === 'tool_call')
  const label = agent === 'paused' ? 'Agente in pausa' : agent === 'working' ? 'L’agente pensa' : 'Ultimo pensiero'
  const tool = action ? String(action.payload.tool) : ''
  return (
    <div className="w-full max-w-[680px] text-center">
      <p className="mb-2 inline-flex items-center gap-1.5 font-mono text-[11px] font-medium tracking-wider text-muted-foreground uppercase">
        <i className="size-1.5 rounded-full bg-live" /> {label}
      </p>
      <p className="text-[17px] leading-snug font-medium text-balance lg:text-xl">
        {thought ? String(thought.payload.text) : 'Ancora nessun pensiero da mostrare.'}
      </p>
      {action && (
        <p className="mt-2.5 font-mono text-xs text-muted-foreground">
          {TOOLS[tool] ?? tool} · {new Date(action.at).toLocaleTimeString('it-IT', { hour: '2-digit', minute: '2-digit' })}
        </p>
      )}
    </div>
  )
}
