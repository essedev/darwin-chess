import { useQuery } from '@tanstack/react-query'
import { useEffect, useState } from 'react'

export type Phase = 'genesis' | 'first_steps' | 'evolution'

export type Gate = { gate: string; passed: boolean; detail: Record<string, unknown> }

export type MatchSummary = {
  opponent: string
  wins: number
  draws: number
  losses: number
  pentanomial: number[] | null
  elo: number | null
  elo_error: number | null
  llr: number | null
  verdict: string | null
  time_control: string
}

export type Experiment = {
  id: number
  phase: Phase
  status: string
  hypothesis: string | null
  rejected_at_gate: string | null
  lesson: string | null
  created_at: string
  gates: Gate[]
  match: MatchSummary | null
}

export type Generation = {
  id: number
  commit: string
  elo_vs_parent: number | null
  elo_absolute: number | null
  hypothesis: string | null
  tried: number
  created_at: string
}

export type AgentEvent = {
  id: number
  experiment_id: number
  kind: 'thought' | 'tool_call' | 'tool_result' | 'status'
  payload: Record<string, unknown>
  at: string
}

export type Overview =
  | { ready: false }
  | {
      ready: true
      phase: Phase
      champion: { id: number; commit: string }
      generations: Generation[]
      experiments: Record<string, number> & { total: number }
      current: Experiment | null
      previous: Experiment | null
      agent: 'working' | 'idle' | 'paused'
      spend: { usd: number; sessions: number; budget: number; quota_now: number }
      events: AgentEvent[]
    }

export type LiveGame = {
  match: string
  game: number
  white: string
  black: string
  fen: string
  san: string[]
  start_ply: number
  last_move: string | null
  result: string | null
  termination: string | null
  tally: Record<string, { wins: number; draws: number; losses: number }>
}

async function getJson<T>(url: string): Promise<T> {
  const response = await fetch(url)
  if (!response.ok) throw new Error(`${url}: ${response.status}`)
  return (await response.json()) as T
}

export function useOverview() {
  return useQuery({
    queryKey: ['overview'],
    queryFn: () => getJson<Overview>('/api/overview'),
    refetchInterval: 5000,
  })
}

/** Live agent events and the game on the board, pushed by the API over SSE. */
export function useLiveStream(initial: AgentEvent[]) {
  const [events, setEvents] = useState<AgentEvent[]>([])
  const [game, setGame] = useState<LiveGame | null>(null)
  const [connected, setConnected] = useState(false)

  useEffect(() => {
    const source = new EventSource('/api/stream')
    source.onopen = () => setConnected(true)
    source.onerror = () => setConnected(false)
    source.addEventListener('agent', (message) => {
      const event = JSON.parse((message as MessageEvent<string>).data) as AgentEvent
      setEvents((previous) => [...previous.slice(-199), event])
    })
    source.addEventListener('game', (message) => {
      setGame(JSON.parse((message as MessageEvent<string>).data) as LiveGame | null)
    })
    return () => source.close()
  }, [])

  const merged = [...initial.filter((e) => !events.some((x) => x.id === e.id)), ...events]
  return { events: merged, game, connected }
}
