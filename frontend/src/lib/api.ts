import { useInfiniteQuery, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'

export type Phase = 'genesis' | 'first_steps' | 'evolution'

export type Gate = { gate: string; passed: boolean; detail: Record<string, unknown> }

/**
 * A short text written by a language model about a game or a match, in both languages. The
 * fields added for the bilingual dashboard are optional: an older API simply leaves them out.
 */
export type Commentary = { it: string | null; en: string | null }

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
  hypothesis_it?: string | null
  rejected_at_gate: string | null
  lesson: string | null
  lesson_it?: string | null
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
  hypothesis_it?: string | null
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
  commentary?: Commentary | null
}

export type LichessPerformance = { games: number; wins: number; draws: number; losses: number; performance: number }

export type Lichess = {
  live: LichessLive | null
  recent: LichessGame[]
  performance: Record<string, LichessPerformance>
}

/** A match the referee judged: a candidate against the random player or the champion. */
export type JudgedMatch = {
  id: number
  experiment_id: number
  kind: string
  opponent: 'random' | 'champion' | string
  wins: number
  draws: number
  losses: number
  pentanomial: number[] | null
  elo: number | null
  elo_error: number | null
  verdict: 'h1' | 'h0' | 'continue' | string | null
  time_control: string
  finished_at: string | null
  hypothesis_en: string | null
  hypothesis_it?: string | null
  commentary?: Commentary | null
}

/** A non-2xx answer from the API; `status` lets a view tell "not found" from "down". */
export class ApiError extends Error {
  readonly status: number
  constructor(url: string, status: number) {
    super(`${url}: ${status}`)
    this.status = status
  }
}

/** A 4xx: the ref, path or id is not there (or not valid); asking again will not change it. */
export const isClientError = (error: Error) => error instanceof ApiError && error.status < 500

/** Retries server hiccups, not answers that will not change. */
const retryUnlessClientError = (count: number, error: Error) => !isClientError(error) && count < 3

async function getJson<T>(url: string): Promise<T> {
  const response = await fetch(url)
  if (!response.ok) throw new ApiError(url, response.status)
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
    refetchInterval: 15000,
  })
}

/** The last judged matches. A 404 means an API without the endpoint yet: not retried. */
export function useMatches() {
  return useQuery({
    queryKey: ['matches'],
    queryFn: () => getJson<JudgedMatch[]>('/api/matches?limit=10'),
    refetchInterval: 15000,
    retry: retryUnlessClientError,
  })
}

/**
 * Live agent events and the game on the board, pushed by the API over SSE. The Lichess game
 * arrives on the same stream and goes into the ['lichess'] query; when it ends the query is
 * refetched, so the finished game shows up among the recent ones. A status event of the agent
 * (a session starts, a candidate goes to judgement) refetches the judged matches.
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
      if (event.kind === 'status') void queryClient.invalidateQueries({ queryKey: ['matches'] })
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

export type DiffStat = { files: number; insertions: number; deletions: number }

export type GenerationDetail = {
  id: number
  commit: string
  parent_commit: string | null
  created_at: string
  elo_vs_parent: number | null
  elo_absolute: number | null
  below_ladder: boolean
  experiment_id: number | null
  hypothesis: string | null
  hypothesis_it?: string | null
  lesson: string | null
  lesson_it?: string | null
  tried: number
  diff_stat: DiffStat | null
  lichess: LichessPerformance | null
}

export type ExperimentRow = {
  id: number
  kind: 'iteration' | 'reflection'
  phase: Phase
  status: string
  trigger: string
  hypothesis: string | null
  hypothesis_it?: string | null
  lesson: string | null
  lesson_it?: string | null
  rejected_at_gate: string | null
  created_at: string
  finished_at: string | null
  base_commit: string | null
  candidate_commit: string | null
  cost_usd: number | null
  gates: Gate[]
  match: MatchSummary | null
}

export type ExperimentPage = { items: ExperimentRow[]; next_before_id: number | null }

export type CodeTree = { ref: string; commit: string; generation: number | null; files: { path: string; size: number }[] }

export type CodeFile = {
  ref: string
  commit: string
  path: string
  size: number
  binary: boolean
  truncated: boolean
  content: string | null
}

export type DiffFile = { path: string; status: string; additions: number; deletions: number; patch: string | null }

export type CodeDiff = { from: string; to: string; files: DiffFile[] }

export type Mind = { strategy: string | null; notes: string | null; system_prompt: string | null; updated_at: string | null }

export type Lab = {
  started_at: string | null
  totals: {
    spend_usd: number
    sessions: number
    iterations: number
    accepted: number
    rejected: number
    llm_calls: number
    input_tokens: number
    cached_tokens: number
    output_tokens: number
    lichess_games: number
  }
  cost_per_generation: { generation: number; usd: number }[]
  changelog: string
  changelog_en?: string | null
}

export function useGenerationsDetail() {
  return useQuery({
    queryKey: ['generations', 'detail'],
    queryFn: () => getJson<GenerationDetail[]>('/api/generations/detail'),
    refetchInterval: 60000,
  })
}

export function useExperiments() {
  return useInfiniteQuery({
    queryKey: ['experiments'],
    queryFn: ({ pageParam }) =>
      getJson<ExperimentPage>(`/api/experiments?limit=50${pageParam === null ? '' : `&before_id=${pageParam}`}`),
    initialPageParam: null as number | null,
    getNextPageParam: (last) => last.next_before_id,
    refetchInterval: 60000,
  })
}

/** A ref the code endpoints understand: gen-N, exp-N or a commit; undefined is the champion. */
export function useCodeTree(ref: string | undefined) {
  return useQuery({
    queryKey: ['code', 'tree', ref ?? 'champion'],
    queryFn: () => getJson<CodeTree>(`/api/code/tree${ref ? `?ref=${encodeURIComponent(ref)}` : ''}`),
    staleTime: 60000,
    retry: retryUnlessClientError,
  })
}

export function useCodeFile(ref: string, path: string | null) {
  return useQuery({
    queryKey: ['code', 'file', ref, path],
    queryFn: () =>
      getJson<CodeFile>(`/api/code/file?ref=${encodeURIComponent(ref)}&path=${encodeURIComponent(path ?? '')}`),
    enabled: path !== null,
    staleTime: Infinity, // keyed by commit, the content never changes
    retry: retryUnlessClientError,
  })
}

/** `spec` is "gen=3" or "exp=12", the query string of /api/code/diff. */
export function useCodeDiff(spec: string | null) {
  return useQuery({
    queryKey: ['code', 'diff', spec],
    queryFn: () => getJson<CodeDiff>(`/api/code/diff?${spec ?? ''}`),
    enabled: spec !== null,
    staleTime: Infinity,
    retry: retryUnlessClientError,
  })
}

export function useMind() {
  return useQuery({ queryKey: ['mind'], queryFn: () => getJson<Mind>('/api/mind'), refetchInterval: 60000 })
}

export function useLab() {
  return useQuery({ queryKey: ['lab'], queryFn: () => getJson<Lab>('/api/lab'), refetchInterval: 60000 })
}
