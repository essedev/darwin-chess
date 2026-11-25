import { useQuery, useQueryClient } from '@tanstack/react-query'
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
      jobs: Jobs
    }

export type Job = { id: number; command: string; created_at: string; max_hours: number }

export type Jobs = {
  running: Job[]
  last_finished:
    | (Job & { status: 'done' | 'failed' | 'killed' | string; exit_code: number | null; finished_at: string | null })
    | null
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

export type LichessLive = {
  game_id: string
  url: string
  generation: number
  color: 'white' | 'black'
  opponent: { name: string; rating: number | null; title: string | null }
  time_control: string
  initial_fen: string
  moves: string[]
  wtime: number
  btime: number
  status: string
  updated_at: string
  fen: string
  san: string[]
  start_ply: number
  last_move: string | null
}

export type LichessResult = 'win' | 'loss' | 'draw' | 'aborted'

export type LichessGame = {
  lichess_id: string
  url: string
  opponent: string
  opponent_rating: number | null
  opponent_title: string | null
  color: 'white' | 'black'
  result: LichessResult | null
  status: string
  generation_id: number
  time_control: string
  finished_at: string | null
}

export type LichessPerformance = { games: number; wins: number; draws: number; losses: number; performance: number }

export type Lichess = {
  live: LichessLive | null
  recent: LichessGame[]
  performance: Record<string, LichessPerformance>
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

export function useLichess() {
  return useQuery({
    queryKey: ['lichess'],
    queryFn: () => getJson<Lichess>('/api/lichess'),
    refetchInterval: 30000,
  })
}

/**
 * Live agent events and the game on the board, pushed by the API over SSE. The Lichess game
 * arrives on the same stream and goes into the ['lichess'] query; when it ends the query is
 * refetched, so the finished game shows up among the recent ones.
 */
export function useLiveStream(initial: AgentEvent[]) {
  const queryClient = useQueryClient()
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
    source.addEventListener('lichess', (message) => {
      const live = JSON.parse((message as MessageEvent<string>).data) as LichessLive | null
      const known = queryClient.getQueryData<Lichess>(['lichess'])
      if (known && live) queryClient.setQueryData<Lichess>(['lichess'], { ...known, live })
      else void queryClient.invalidateQueries({ queryKey: ['lichess'] })
    })
    return () => source.close()
  }, [queryClient])

  const merged = [...initial.filter((e) => !events.some((x) => x.id === e.id)), ...events]
  return { events: merged, game, connected }
}
