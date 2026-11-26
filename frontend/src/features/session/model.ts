import type { AgentEvent } from '@/lib/api'
import type { Context, Say } from './describe-bash'
import { type Desc, describe, type Outcome, outcome } from './describe'
import { parsePyRepr } from './shell'

/**
 * A session's events as the log reads them: every tool call with its answer, the thoughts and
 * the reasoning in between, the status lines. Works on both payload formats: arguments as a
 * JSON object with the call id (from 2026-11-26), or the old repr string paired by order.
 */

export type Result = { id: number; at: string; text: string; error: boolean; cut: boolean }

export type Call = {
  type: 'call'
  id: number
  at: string
  tool: string
  args: Record<string, unknown>
  /** The stored text when the arguments could not be read as an object (old rows). */
  rawArgs: string | null
  /** The stored arguments were cut: a field (new rows) or the whole repr (old rows). */
  cut: boolean
  legacy: boolean
  desc: Desc
  result: Result | null
  out: Outcome | null
}

export type Note = { type: 'thought' | 'reasoning'; id: number; at: string; text: string; italian: string | null; cut: boolean }

export type Status = { type: 'status'; id: number; at: string; state: string; payload: Record<string, unknown> }

export type Item = Call | Note | Status

export type SessionModel = {
  items: Item[]
  calls: Call[]
  /** The newest call still waiting for its answer. */
  pending: Call | null
  thoughts: number
  reasonings: number
  started: string | null
  last: string | null
}

const textOf = (value: unknown) => (typeof value === 'string' ? value : '')
/** Old rows mark a cut text only by its length and the trailing dots. */
const legacyCut = (text: string) => text.length > 2000 && text.endsWith('...')

function argsOf(raw: unknown): { args: Record<string, unknown>; rawArgs: string | null; cut: boolean; legacy: boolean } {
  if (raw && typeof raw === 'object' && !Array.isArray(raw)) return { args: raw as Record<string, unknown>, rawArgs: null, cut: false, legacy: false }
  const text = textOf(raw)
  const parsed = parsePyRepr(text)
  const value = parsed.value
  if (value && typeof value === 'object' && !Array.isArray(value)) return { args: value as Record<string, unknown>, rawArgs: text, cut: parsed.cut, legacy: true }
  return { args: {}, rawArgs: text, cut: legacyCut(text), legacy: true }
}

export function buildSession(say: Say, events: AgentEvent[]): SessionModel {
  const ctx: Context = { logs: {}, worktrees: new Set() }
  const items: Item[] = []
  const byId = new Map<string, Call>()
  const queues = new Map<string, Call[]>() // old rows: a result answers the oldest open call of its tool
  for (const e of [...events].sort((a, b) => a.id - b.id)) {
    const p = e.payload
    if (e.kind === 'tool_call') {
      const tool = textOf(p.tool)
      const read = argsOf(p.args)
      const cut = read.cut || p.cut === true
      const call: Call = { type: 'call', id: e.id, at: e.at, tool, ...read, cut, desc: describe(say, tool, read.args, cut, ctx), result: null, out: null }
      const callId = textOf(p.call_id)
      if (callId) byId.set(callId, call)
      else queues.set(tool, [...(queues.get(tool) ?? []), call])
      items.push(call)
    } else if (e.kind === 'tool_result') {
      const callId = textOf(p.call_id)
      const tool = textOf(p.tool)
      const call = callId ? byId.get(callId) : queues.get(tool)?.shift()
      if (!call || call.result) continue
      const text = textOf(p.text)
      const cut = typeof p.cut === 'boolean' ? p.cut : legacyCut(text)
      call.result = { id: e.id, at: e.at, text, error: p.error === true, cut }
      call.out = outcome(say, call.tool, call.desc, text, call.result.error, cut, ctx)
    } else if (e.kind === 'thought' || e.kind === 'reasoning') {
      const text = textOf(p.text)
      const cut = typeof p.cut === 'boolean' ? p.cut : legacyCut(text)
      items.push({ type: e.kind, id: e.id, at: e.at, text, italian: e.text_it ?? null, cut })
    } else if (e.kind === 'status') {
      items.push({ type: 'status', id: e.id, at: e.at, state: textOf(p.state), payload: p })
    }
  }
  const calls = items.filter((i): i is Call => i.type === 'call')
  const started = items.find((i) => i.type === 'status' && i.state === 'started')?.at ?? items[0]?.at ?? null
  const lastEvent = events.length ? events.reduce((a, b) => (a.id > b.id ? a : b)).at : null
  return {
    items,
    calls,
    pending: calls.filter((c) => !c.result).pop() ?? null,
    thoughts: items.filter((i) => i.type === 'thought').length,
    reasonings: items.filter((i) => i.type === 'reasoning').length,
    started,
    last: lastEvent,
  }
}

/** The events of one session among the stream's, merged with what the API returned; the
    API's copy wins (it carries the Italian of a thought). */
export function mergeEvents(base: AgentEvent[], streamed: AgentEvent[], experimentId: number): AgentEvent[] {
  const known = new Set(base.map((e) => e.id))
  const extra = streamed.filter((e) => e.experiment_id === experimentId && !known.has(e.id))
  return extra.length ? [...base, ...extra].sort((a, b) => a.id - b.id) : base
}
