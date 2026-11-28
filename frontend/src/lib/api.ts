import { keepPreviousData, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'

export type Phase = 'genesis' | 'first_steps' | 'evolution'

export type Gate = { gate: string; passed: boolean; detail: Record<string, unknown> }

/**
 * A short text written by a language model about a game or a match, in both languages. The
 * fields added for the bilingual dashboard are optional: an older API simply leaves them out.
 */
export type Commentary = { it: string | null; en: string | null }

/** The match of the experiment on trial so far, rewritten after every SPRT batch. */
export type MatchProgress = {
  games: number
  wins: number
  draws: number
  losses: number
  llr: number
  /** Null until the first batch is played: the referee is still building and checking. */
  bounds: [number, number] | null
}

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
  title?: Commentary | null
  progress?: MatchProgress | null
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
  elo_absolute_error?: number | null
  title?: Commentary | null
  hypothesis: string | null
  hypothesis_it?: string | null
  tried: number
  created_at: string
}

export type AgentEvent = {
  id: number
  experiment_id: number
  /** `reasoning` is the model's summarized thinking, kept in English (DATABASE_SCHEMA.md). */
  kind: 'thought' | 'reasoning' | 'tool_call' | 'tool_result' | 'status'
  payload: Record<string, unknown>
  /** A thought's Italian, a few seconds after it: the overview carries it, the stream does not. */
  text_it?: string | null
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
      /** The experiment the referee is judging now (the queued ones are "judging" too). */
      on_trial?: Experiment | null
      previous: Experiment | null
      agent: 'working' | 'idle' | 'paused'
      spend: {
        usd: number
        sessions: number
        budget: number
        quota_now: number
        /** The agent's model id and reasoning effort, e.g. "claude-haiku-5-5", "high". */
        model: string
        effort: string
        /** Today's tokens. Input: at full price, read from the prompt cache, written to it. */
        tokens: { input: number; cached: number; cache_write: number; output: number }
      }
      events: AgentEvent[]
      jobs: Jobs
    }

/** A long job running now. `purpose` is the agent's sentence, in English; null on old jobs. */
export type Job = {
  id: number
  experiment_id: number
  purpose: string | null
  command: string
  created_at: string
  max_hours: number
}

/** The jobs running now: how a job ended is on the page of the session that started it. */
export type Jobs = { running: Job[] }

/** A job as the session that started it shows it. `reason`: why it failed or was stopped. */
export type SessionJob = {
  id: number
  purpose: string | null
  command: string
  status: 'running' | 'done' | 'failed' | 'killed' | string
  exit_code: number | null
  reason: string | null
  max_hours: number
  created_at: string
  finished_at: string | null
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
  /** Games of this batch still being played: while any is, its tally is not in the trial's progress. */
  running?: number
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
  profile_url?: string | null
  recent: LichessGame[]
  performance: Record<string, LichessPerformance>
}

/** How a move changed the winning chances, judged the way Lichess judges it. */
export type Judgement = 'blunder' | 'mistake' | 'inaccuracy'

/** One side's moves of a game: how many of each judgement, and the average centipawn loss. */
export type SideReview = Record<Judgement, number> & { acpl: number | null }

/** Lichess's speeds, by base time plus 40 increments. */
export type Speed = 'ultrabullet' | 'bullet' | 'blitz' | 'rapid' | 'classical' | 'correspondence'

/** A finished game in the history list; `curve` and `ours` only when Stockfish analysed it. */
export type LichessHistoryGame = LichessGame & {
  id: number
  rated: boolean
  speed: Speed
  plies: number
  /** The bot's winning chances over the game, -100 to 100, at most 32 points. */
  curve: number[] | null
  ours: SideReview | null
}

export type LichessGamesPage = {
  items: LichessHistoryGame[]
  next_before_id: number | null
  /** Per result under the generation and rated filters, not the result one. */
  counts: Record<'win' | 'draw' | 'loss' | 'total', number>
  generations: { id: number; games: number }[]
  speeds: { id: Speed; games: number }[]
  performance: Record<string, LichessPerformance>
  profile_url: string | null
}

/** A position after a move (the first one is the start); evaluation and chances from the bot's side. */
export type GamePosition = { fen: string; eval_cp?: number; chances?: number }

export type GameMove = { uci: string; san: string; ours: boolean; judgement: Judgement | null }

/** One finished game move by move: `positions` has one more entry than `moves`. */
export type LichessGameDetail = LichessGame & {
  id: number
  rated: boolean
  speed: Speed
  rating_after: number | null
  analysed: boolean
  positions: GamePosition[]
  moves: GameMove[]
  sides: { us: SideReview; them: SideReview } | null
  /** The index of the move where the game turned. */
  turning_point: number | null
  older: string | null
  newer: string | null
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
  title?: Commentary | null
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
 * (a session starts, a candidate goes to judgement) refetches the judged matches and that session.
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
      if (event.kind === 'status') {
        void queryClient.invalidateQueries({ queryKey: ['matches'] })
        void queryClient.invalidateQueries({ queryKey: ['session', event.experiment_id] })
      }
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

  // The overview refetches every few seconds and brings the Italian of a thought once it
  // is written; the stream's copy of the same event never has it.
  const translated = new Map(initial.filter((e) => e.text_it).map((e) => [e.id, e]))
  const merged = [
    ...initial.filter((e) => !events.some((x) => x.id === e.id)),
    ...events.map((e) => translated.get(e.id) ?? e),
  ]
  return { events: merged, game, connected }
}

export type DiffStat = { files: number; insertions: number; deletions: number }

export type GenerationDetail = {
  id: number
  commit: string
  parent_commit: string | null
  created_at: string
  elo_vs_parent: number | null
  elo_vs_parent_error?: number | null
  /** The joint estimate: games against Stockfish and matches between champions together. */
  elo_absolute: number | null
  elo_absolute_error?: number | null
  /** The latest measure from the Stockfish games alone, as recorded. */
  elo_anchors?: number | null
  elo_anchors_error?: number | null
  below_ladder: boolean
  experiment_id: number | null
  title?: Commentary | null
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
  generation_id?: number | null
  title?: Commentary | null
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

export type ExperimentPage = {
  items: ExperimentRow[]
  next_before_id: number | null
  counts?: Record<string, number> & { total: number }
}

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

export type Mind = {
  strategy: string | null
  notes: string | null
  system_prompt: string | null
  /** The Italian of exactly the version above, null until it is translated. */
  strategy_it?: string | null
  notes_it?: string | null
  system_prompt_it?: string | null
  updated_at: string | null
}

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

/** One page of experiments below `beforeId` (null: the newest), only with these statuses. */
export function useExperimentPage(statuses: readonly string[], beforeId: number | null, limit = 10) {
  const params = new URLSearchParams({ limit: String(limit) })
  if (statuses.length) params.set('status', statuses.join(','))
  if (beforeId !== null) params.set('before_id', String(beforeId))
  return useQuery({
    queryKey: ['experiments', statuses.join(','), beforeId, limit],
    queryFn: () => getJson<ExperimentPage>(`/api/experiments?${params.toString()}`),
    placeholderData: keepPreviousData,
    refetchInterval: 60000,
  })
}

export type LichessFilter = {
  generation: number | null
  result: 'win' | 'draw' | 'loss' | null
  rated: boolean
  /** A piece of the opponent's name. */
  q: string
  opponent: 'bot' | 'human' | null
  speed: Speed | null
}

/** One page of finished Lichess games below `beforeId` (null: the newest). */
export function useLichessGames(filter: LichessFilter, beforeId: number | null, limit = 20) {
  const params = new URLSearchParams({ limit: String(limit) })
  if (filter.generation !== null) params.set('generation', String(filter.generation))
  if (filter.result) params.set('result', filter.result)
  if (filter.rated) params.set('rated', 'true')
  if (filter.q) params.set('q', filter.q)
  if (filter.opponent) params.set('opponent', filter.opponent)
  if (filter.speed) params.set('speed', filter.speed)
  if (beforeId !== null) params.set('before_id', String(beforeId))
  return useQuery({
    queryKey: ['lichess-games', params.toString()],
    queryFn: () => getJson<LichessGamesPage>(`/api/lichess/games?${params.toString()}`),
    placeholderData: keepPreviousData,
    refetchInterval: 60000,
    retry: retryUnlessClientError,
  })
}

/** One finished game; it never changes, so it is read once. */
export function useLichessGame(lichessId: string | null) {
  return useQuery({
    queryKey: ['lichess-game', lichessId],
    queryFn: () => getJson<LichessGameDetail>(`/api/lichess/games/${encodeURIComponent(lichessId ?? '')}`),
    enabled: lichessId !== null,
    staleTime: Infinity,
    retry: retryUnlessClientError,
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

/** One agent session with its events in order, its outcome and its neighbours. */
export type SessionDetail = {
  id: number
  kind: 'iteration' | 'reflection'
  phase: Phase
  status: string
  trigger: string
  base_generation_id: number | null
  generation_id: number | null
  title: Commentary | null
  hypothesis: string | null
  hypothesis_it: string | null
  rejected_at_gate: string | null
  candidate_commit: string | null
  created_at: string
  finished_at: string | null
  cost_usd: number
  gates: Gate[]
  match: MatchSummary | null
  /** The long jobs this session started, oldest first. */
  jobs: SessionJob[]
  events: AgentEvent[]
  /** More events than the endpoint returns: these are the first ones. */
  truncated: boolean
  previous: number | null
  next: number | null
  /** Today's limits of a session (an older one may have had others). */
  limits: { minutes: number; tool_calls: number }
}

/**
 * A session, refetched every `everyMs` while it runs (the stream fills the gaps in between;
 * a refetch brings the Italian of the thoughts and the final status). Null id: disabled.
 */
export function useSession(id: number | null, everyMs: number | false) {
  return useQuery({
    queryKey: ['session', id],
    queryFn: () => getJson<SessionDetail>(`/api/sessions/${id ?? ''}`),
    enabled: id !== null,
    refetchInterval: (query) => (query.state.data && query.state.data.status !== 'running' ? false : everyMs),
    retry: retryUnlessClientError,
  })
}

export function useMind() {
  return useQuery({ queryKey: ['mind'], queryFn: () => getJson<Mind>('/api/mind'), refetchInterval: 60000 })
}

export function useLab() {
  return useQuery({ queryKey: ['lab'], queryFn: () => getJson<Lab>('/api/lab'), refetchInterval: 60000 })
}
