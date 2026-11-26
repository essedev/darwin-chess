import { type Cat, type Context, describeBash, noteOf, type Say } from './describe-bash'
import { basename } from './shell'

/**
 * A tool call and its answer in words for a visitor (concept D, variant A), by fixed rules on
 * the payload: the tool, then the command or the file. The raw call is always a click away.
 */

export type Desc = { cat: Cat; text: string; wait: number | null; engines: string[] | null }

export type Outcome = { text: string; tone: '' | 'good' | 'bad' | 'warn'; mono?: boolean }

/** The colour of an outcome's words. */
export const TONE: Record<Outcome['tone'], string> = { '': 'text-muted-foreground', good: 'text-good', bad: 'text-bad', warn: 'text-c-spend' }

const str = (value: unknown) => (typeof value === 'string' ? value : value == null ? '' : String(value))
const num = (value: unknown) => (typeof value === 'number' ? value : null)

/** Line diff of an edit (LCS), for the count of lines and the diff view. */
export function lineDiff(a: string, b: string): [' ' | '-' | '+', string][] {
  const A = a.split('\n')
  const B = b.split('\n')
  const n = A.length
  const m = B.length
  const L = Array.from({ length: n + 1 }, () => new Int32Array(m + 1))
  const at = (i: number, j: number) => L[i]?.[j] ?? 0
  for (let i = n - 1; i >= 0; i--) {
    const row = L[i]
    if (!row) continue
    for (let j = m - 1; j >= 0; j--) row[j] = A[i] === B[j] ? at(i + 1, j + 1) + 1 : Math.max(at(i + 1, j), at(i, j + 1))
  }
  const out: [' ' | '-' | '+', string][] = []
  let i = 0
  let j = 0
  while (i < n && j < m) {
    if (A[i] === B[j]) {
      out.push([' ', A[i] ?? ''])
      i++
      j++
    } else if (at(i + 1, j) >= at(i, j + 1)) out.push(['-', A[i++] ?? ''])
    else out.push(['+', B[j++] ?? ''])
  }
  while (i < n) out.push(['-', A[i++] ?? ''])
  while (j < m) out.push(['+', B[j++] ?? ''])
  return out
}

export type Edit = { oldText: string; newText: string }

/** The changes of an edit call; pi's edit tool takes `edits`, older ones `oldText`/`newText`. */
export function editsOf(args: Record<string, unknown>): Edit[] {
  const list = Array.isArray(args.edits) ? args.edits : [args]
  return list
    .filter((e): e is Record<string, unknown> => typeof e === 'object' && e !== null && ('oldText' in e || 'newText' in e))
    .map((e) => ({ oldText: str(e.oldText), newText: str(e.newText) }))
}

function editCount(edits: Edit[]) {
  let add = 0
  let del = 0
  for (const e of edits) for (const [k] of lineDiff(e.oldText, e.newText)) if (k === '+') add++; else if (k === '-') del++
  return { add, del }
}

function describeEdit(say: Say, path: string, args: Record<string, unknown>, cut: boolean): Desc {
  const file = basename(path)
  const base = { wait: null, engines: null }
  if (path.startsWith('/memory/')) {
    const note = noteOf(file)
    return note ? { ...base, cat: 'deliver', text: say.t('do.updateNote', { what: say.t(note) }) }
      : { ...base, cat: 'try', text: say.t('do.toolEdit', { file }) }
  }
  const { add, del } = editCount(editsOf(args))
  if (!add && !del) return { ...base, cat: 'edit', text: say.t('do.editFile', { file }) }
  const signed = [add ? `+${add}` : '', del ? `−${del}` : ''].filter(Boolean).join(' ')
  return { ...base, cat: 'edit', text: say.t(cut ? 'do.editLinesCut' : 'do.editLines', { file, lines: signed }) }
}

function describeWrite(say: Say, path: string, content: string, cut: boolean): Desc {
  const file = basename(path)
  const base = { wait: null, engines: null }
  const lines = cut ? null : content.split('\n').length
  if (path.startsWith('/memory/')) {
    const note = noteOf(file)
    if (note) return { ...base, cat: 'deliver', text: say.t('do.rewriteNote', { what: say.t(note) }) }
    const sized = lines ? `${file} (${say.tn('count.lines', lines)})` : file
    return { ...base, cat: 'try', text: say.t('do.toolWrite', { file: sized }) }
  }
  return { ...base, cat: 'edit', text: say.t('do.write', { file }) }
}

/** A call in words; `ctx` carries what earlier calls of the session established. */
export function describe(say: Say, tool: string, args: Record<string, unknown>, cut: boolean, ctx: Context): Desc {
  const { t } = say
  const base = { wait: null, engines: null }
  const path = str(args.path)
  const limit = num(args.limit)
  switch (tool) {
    case 'bash':
      return describeBash(say, str(args.command), ctx)
    case 'read': {
      const offset = num(args.offset)
      const file = basename(path)
      const text = offset && limit ? t('do.readLines', { file, ranges: `${offset}-${offset + limit - 1}` }) : t('do.read', { file })
      return { ...base, cat: 'understand', text }
    }
    case 'edit':
      return describeEdit(say, path, args, cut)
    case 'write':
      return describeWrite(say, path, str(args.content), cut)
    case 'experiments': {
      const query = str(args.query)
      const text = query ? t('do.experimentsQuery', { query }) : limit ? t('do.experimentsLast', { n: limit }) : t('do.experiments')
      return { ...base, cat: 'understand', text }
    }
    case 'lichess_losses':
      return { ...base, cat: 'understand', text: limit ? t('do.lossesLast', { n: limit }) : t('do.losses') }
    case 'perft_check': {
      const depth = num(args.depth)
      return { ...base, cat: 'try', text: depth ? t('do.perftDepth', { n: depth }) : t('do.perft') }
    }
    case 'submit':
      return { ...base, cat: 'deliver', text: t('do.submit') }
    case 'run_job': {
      const action = str(args.action)
      if (action === 'status') return { ...base, cat: 'understand', text: t('do.jobStatus') }
      if (action === 'delete') return { ...base, cat: 'understand', text: t('do.jobDelete', { id: str(args.job_id) }) }
      return { ...base, cat: 'try', text: t('do.jobStart') }
    }
    default:
      return { ...base, cat: 'understand', text: t('do.tool', { name: tool }) }
  }
}

const firstLine = (text: string) => (text.split('\n').find((x) => x.trim()) ?? '').trim()
const clip = (text: string, n: number) => (text.length > n ? `${text.slice(0, n - 1)}…` : text)

/** "nuova 29 · partenza 24 · patte 7": which engine is which comes from where it was built. */
function matchText(say: Say, w: number, d: number, l: number, engines: string[] | null, ctx: Context): string {
  const role = (path: string | undefined) =>
    !path ? null : path.startsWith('/genome/') ? 'new' : [...ctx.worktrees].some((x) => path.startsWith(`${x}/`)) ? 'start' : null
  const [a, b] = engines ? [role(engines[0]), role(engines[1])] : [null, null]
  if (a === 'start' && b === 'new') return say.t('out.matchRoles', { mine: l, theirs: w, d })
  if (a === 'new' && b === 'start') return say.t('out.matchRoles', { mine: w, theirs: l, d })
  return say.t('out.match', { w, l, d })
}

/** What came back, in a few words. */
export function outcome(say: Say, tool: string, desc: Desc, text: string, error: boolean, cut: boolean, ctx: Context): Outcome {
  const { t, tn, f } = say
  if (error) return { tone: 'bad', text: t('out.error', { text: clip(firstLine(text), 70) }) }
  const lines = text.split('\n').filter((x) => x.trim()).length
  const more = cut ? t('out.andMore') : ''
  switch (tool) {
    case 'edit':
    case 'write':
      return /Successfully/.test(text) ? { tone: 'good', text: t('out.done') } : { tone: '', text: clip(firstLine(text), 70), mono: true }
    case 'perft_check': {
      const m = /^OK: (\d+) position/.exec(text)
      return m ? { tone: 'good', text: t('out.perftOk', { n: m[1] ?? '' }) } : { tone: 'bad', text: t('out.perftBad') }
    }
    case 'submit':
      return /^Submitted/.test(text) ? { tone: 'good', text: t('out.submitted') } : { tone: 'bad', text: clip(firstLine(text), 70) }
    case 'experiments':
      return { tone: '', text: tn('count.attempts', (text.match(/^#\d+ /gm) ?? []).length) + more }
    case 'lichess_losses': {
      const m = /(\d+) most recent/.exec(text)
      return { tone: '', text: m ? tn('count.lost', Number(m[1])) : clip(firstLine(text), 70) }
    }
    case 'read':
      return { tone: '', text: tn('count.lines', lines) + more }
  }
  const final = [...text.matchAll(/final A vs B: W(\d+) D(\d+) L(\d+)/g)].pop()
  if (final) return { tone: '', text: matchText(say, Number(final[1]), Number(final[2]), Number(final[3]), desc.engines, ctx) }
  const progress = [...text.matchAll(/game (\d+): .*?W(\d+) D(\d+) L(\d+)/g)].pop()
  if (progress) {
    const score = matchText(say, Number(progress[2]), Number(progress[3]), Number(progress[4]), desc.engines, ctx)
    return { tone: '', text: t('out.after', { n: Number(progress[1]) + 1, score }) }
  }
  if (/error(\[E\d+\])?:/.test(text) && /-->|could not compile/.test(text)) return { tone: 'bad', text: t('out.noBuild') }
  const notes: string[] = []
  const missingModule = /ModuleNotFoundError: No module named '(\w+)'/.exec(text)
  if (missingModule) notes.push(t('out.noModule', { name: missingModule[1] ?? '' }))
  const missingCommand = /([\w-]+): command not found/.exec(text)
  if (missingCommand) notes.push(t('out.noCommand', { name: missingCommand[1] ?? '' }))
  const moves = (text.match(/^bestmove \S+/gm) ?? []).length
  const reals = [...text.matchAll(/^real\s+(\d+)m([\d.]+)s/gm)].map((m) => Number(m[1]) * 60 + Number(m[2]))
  if (moves) {
    const secs = (x: number) => (x < 1 ? `${Math.round(x * 1000)} ms` : `${f.num(Math.round(x * 10) / 10)} s`)
    const first = reals[0]
    const timing = first === undefined ? ''
      : reals.length > 1 && reals.length === moves ? t('out.eachIn', { time: secs(first) })
      : moves === 1 ? t('out.in', { time: secs(first) })
      : t('out.timed', { time: secs(first) })
    notes.push(tn('count.moves', moves) + timing)
  }
  if (!notes.length && /Finished `release`/.test(text)) notes.push(t('out.builds'))
  if (notes.length) return { tone: missingModule || missingCommand ? 'warn' : '', text: notes.join(', ') }
  if (text.trim() === '(no output)' || !text.trim()) return { tone: '', text: t('out.silent') }
  if (desc.cat === 'understand') return { tone: '', text: tn('count.lines', lines) + more }
  if (desc.cat === 'deliver' || desc.cat === 'edit') return { tone: 'good', text: t('out.done') }
  return { tone: '', text: clip(firstLine(text), 64), mono: true }
}
