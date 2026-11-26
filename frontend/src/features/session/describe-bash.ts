import type { I18n } from '@/i18n/context'
import { basename, type Command, maskHeredocs, parseCommand, splitSegments } from './shell'

/**
 * A bash command in words for a visitor, by fixed rules on the command (concept D, variant A):
 * split into simple commands, filters after a pipe and housekeeping (cd, echo, rm...) left out,
 * what is left said in at most three phrases. No model writes these sentences.
 */

export type Say = Pick<I18n, 't' | 'tn' | 'f'>

/** What a call does: understand, change the engine, try something, wait, hand in. */
export type Cat = 'understand' | 'edit' | 'try' | 'wait' | 'deliver'

/** What earlier calls established: where a test match writes its log, the worktrees made. */
export type Context = { logs: Record<string, MatchRun>; worktrees: Set<string> }

export type MatchRun = { engines: string[]; games: number | null; bg: boolean }

type Part = {
  cat: Cat
  key: string
  text?: string
  wait?: number
  file?: string
  ranges?: [number, number][]
  logs?: string[]
  exps?: string[]
  runs?: MatchRun[]
  engines?: string[] | null
}

export type BashDesc = { cat: Cat; text: string; wait: number | null; engines: string[] | null }

/** Memory files the agent keeps, by name. */
export const NOTE_FILES = { 'NOTES.md': 'note.notes', 'STRATEGY.md': 'note.strategy', 'CONTRACT.md': 'note.contract' } as const
export const noteOf = (file: string) => NOTE_FILES[file as keyof typeof NOTE_FILES] ?? null

const FILTERS = new Set(['head', 'tail', 'grep', 'sort', 'uniq', 'wc', 'cut', 'awk', 'sed', 'tr', 'tee', 'xargs', 'cat', 'less'])
const QUIET = new Set(['cd', 'echo', 'printf', 'rm', 'export', 'true', 'do', 'done', 'then', 'fi', 'if', 'mkdir', 'set',
  'chmod', 'touch', 'cp', 'mv', 'exit', 'wait', 'kill', 'pkill', 'source', 'else', 'elif'])

/** "a, b and c" in the visitor's language. */
export function joinWords(say: Say, words: string[]): string {
  if (words.length <= 1) return words.join('')
  return `${words.slice(0, -1).join(', ')}${say.t('do.and')}${words[words.length - 1]}`
}

/** "15 minuti", "40 secondi". */
export function durationWords(say: Say, seconds: number): string {
  return seconds < 60 ? say.tn('count.seconds', seconds) : say.tn('count.minutes', Math.round(seconds / 60))
}

function readFile(say: Say, file: string): Part {
  const name = basename(file)
  const note = noteOf(name)
  if (note) return { cat: 'understand', key: `note:${name}`, text: say.t('do.reread', { what: say.t(note) }) }
  if (/\.log$/.test(file)) return { cat: 'understand', key: 'log', logs: [file] }
  return { cat: 'understand', key: `read:${file}`, file }
}

function pythonBody(say: Say, body: string): Part {
  if (/\.write\(/.test(body)) {
    const files = body.match(/[\w/.-]+\.(?:md|py|rs|toml)\b/g) ?? []
    const file = files.find((x) => noteOf(basename(x))) ?? files[0]
    if (file) {
      const name = basename(file)
      const note = noteOf(name)
      if (note) return { cat: 'deliver', key: `note-write:${name}`, text: say.t('do.updateNote', { what: say.t(note) }) }
      if (/\.rs$/.test(name)) return { cat: 'edit', key: `edit:${name}`, text: say.t('do.editFile', { file: name }) }
      return { cat: 'try', key: `tool-edit:${name}`, text: say.t('do.toolEdit', { file: name }) }
    }
  }
  const imported = /sys\.path\.insert\([^)]*\/memory[^)]*\)[\s\S]*?import\s+(\w+)/.exec(body)
  if (imported) return { cat: 'try', key: `tool-try:${imported[1]}`, text: say.t('do.toolTry', { file: `${imported[1]}.py` }) }
  return { cat: 'try', key: 'py', text: say.t('do.python') }
}

function python(say: Say, s: Command, ctx: Context, bodies: string[]): Part {
  const a = s.args
  if (a[0] === '-c') {
    const m = /import\s+(\w+)/.exec(a[1] ?? '')
    return { cat: 'understand', key: 'module', text: m ? say.t('do.module', { name: m[1] ?? '' }) : say.t('do.pythonLine') }
  }
  if (a[0] === '-') {
    const heredoc = /<<HEREDOC(\d+)/.exec(s.raw)
    return pythonBody(say, heredoc ? bodies[Number(heredoc[1])] ?? '' : '')
  }
  const script = a.find((x) => /\.py$/.test(x))
  if (!script) return { cat: 'try', key: 'py', text: say.t('do.python') }
  const name = basename(script)
  if (name === 'match.py') {
    const rest = a.slice(a.indexOf(script) + 1)
    const run: MatchRun = { engines: rest.slice(0, 2), games: Number.parseInt(rest[2] ?? '', 10) || null, bg: s.bg }
    if (s.out) ctx.logs[s.out] = run
    return { cat: 'try', key: 'match', runs: [run] }
  }
  return { cat: 'try', key: `tool:${name}`, text: say.t('do.toolRun', { file: name }) }
}

function git(say: Say, args: string[], ctx: Context): Part {
  const sub = args[0] ?? ''
  if (sub === 'status' || sub === 'log') return { cat: 'understand', key: 'history', text: say.t('do.history') }
  if (sub === 'diff' || sub === 'show') {
    // Saved versions: refs/darwin/exp-N and wip-N are attempts (#N), gen-N the champions.
    const refs = args
      .map((x) => /\b(exp|wip|gen)-(\d+)/.exec(x))
      .filter((m): m is RegExpExecArray => m !== null)
      .map((m) => (m[1] === 'gen' ? `gen-${m[2]}` : `#${m[2]}`))
    if (refs.length) return { cat: 'understand', key: sub, exps: refs }
    return sub === 'diff' ? { cat: 'understand', key: 'diff0', text: say.t('do.diffWorking') } : { cat: 'understand', key: 'git', text: say.t('do.git', { sub }) }
  }
  if (sub === 'show-ref') return { cat: 'understand', key: 'refs', text: say.t('do.refs') }
  if (sub === 'worktree' && args[1] === 'add') {
    const dir = args.slice(2).find((x) => !x.startsWith('-'))
    if (dir) ctx.worktrees.add(dir.replace(/\/+$/, ''))
    return { cat: 'try', key: 'worktree', text: say.t('do.worktree') }
  }
  return { cat: 'understand', key: 'git', text: say.t('do.git', { sub }).trim() }
}

function classify(say: Say, s: Command, ctx: Context, bodies: string[], loop: { n: number }): Part | null {
  const { cmd, args } = s
  const name = basename(cmd)
  if (!cmd) return null
  if (s.piped && FILTERS.has(name)) return null
  if (cmd === 'for') {
    const k = args.indexOf('in')
    loop.n = k >= 0 ? args.length - k - 1 : 0
    return null
  }
  if (QUIET.has(name) || /^\w+=/.test(cmd)) return null
  if (name === 'sleep') {
    const n = Number.parseInt(args[0] ?? '', 10)
    return n >= 30 ? { cat: 'wait', key: 'sleep', text: say.t('do.sleep', { time: durationWords(say, n) }), wait: n } : null
  }
  if (name === 'cargo') {
    if (args[0] === 'build') return { cat: 'try', key: 'build', text: say.t('do.build') }
    if (args[0] === 'test') return { cat: 'try', key: 'test', text: say.t('do.test') }
    return { cat: 'try', key: 'cargo', text: say.t('do.cargo', { sub: args[0] ?? '' }).trim() }
  }
  if (/target\/release\/genome$/.test(cmd)) return { cat: 'try', key: 'engine' }
  if (/^python3?$/.test(name)) return python(say, s, ctx, bodies)
  if (name === 'sed') {
    const range = args.find((x) => /^\d+,\d+p$/.test(x))
    const file = args.filter((x) => !x.startsWith('-') && x !== range).pop()
    if (range && file) {
      const [a, b] = range.slice(0, -1).split(',').map(Number)
      return { cat: 'understand', key: `read:${file}`, file, ranges: [[a ?? 0, b ?? 0]] }
    }
    return { cat: 'understand', key: 'sed', text: say.t('do.sed') }
  }
  if (['cat', 'head', 'tail', 'less'].includes(name)) {
    const file = args.filter((x) => !x.startsWith('-') && !/^\d+$/.test(x)).pop()
    return file ? readFile(say, file) : null
  }
  if (name === 'grep' || name === 'rg') {
    const words = args.filter((x) => !x.startsWith('-'))
    const pattern = words[0] ?? ''
    const file = words[1] ? basename(words[1]) : say.t('do.theCode')
    if (/fn /.test(pattern)) return { cat: 'understand', key: `grep-fn:${file}`, text: say.t('do.grepFn', { file }) }
    return { cat: 'understand', key: `grep:${pattern}`, text: say.t('do.grep', { pattern, file }) }
  }
  if (name === 'git') return git(say, args, ctx)
  if (name === 'ls') {
    const dirs = args.filter((x) => !x.startsWith('-')).map((x) => x.replace(/\/+$/, ''))
    return { cat: 'understand', key: 'ls', text: dirs.length ? say.t('do.lsIn', { dirs: joinWords(say, dirs) }) : say.t('do.ls') }
  }
  if (name === 'wc') return { cat: 'understand', key: 'wc', text: say.t('do.wc') }
  if (['which', 'nproc', 'uname', 'free', 'df', 'du'].includes(name)) return { cat: 'understand', key: 'env', text: say.t('do.env') }
  return { cat: 'understand', key: `cmd:${name}`, text: say.t('do.cmd', { name }) }
}

/** Parts that say the same thing (two sed ranges of one file, two match runs) become one. */
function merge(parts: Part[]): Part[] {
  const merged: Part[] = []
  const byKey = new Map<string, Part>()
  for (const p of parts) {
    const prev = byKey.get(p.key)
    if (prev) {
      prev.ranges?.push(...(p.ranges ?? []))
      prev.logs?.push(...(p.logs ?? []))
      prev.exps?.push(...(p.exps ?? []))
      prev.runs?.push(...(p.runs ?? []))
      continue
    }
    const q: Part = { ...p, ranges: [...(p.ranges ?? [])], logs: [...(p.logs ?? [])], exps: [...(p.exps ?? [])], runs: [...(p.runs ?? [])] }
    byKey.set(p.key, q)
    merged.push(q)
  }
  return merged
}

/** The sentence of a part whose words depend on its merged details. */
function finish(say: Say, q: Part, ctx: Context, masked: string, loop: number) {
  const { t, tn } = say
  if (q.key.startsWith('read:') && q.file) {
    const file = basename(q.file)
    const ranges = q.ranges ?? []
    q.text = ranges.length ? t('do.readLines', { file, ranges: joinWords(say, ranges.map(([a, b]) => `${a}-${b}`)) }) : t('do.read', { file })
  }
  if (q.key === 'diff' || q.key === 'show') {
    const refs = [...new Set(q.exps)]
    const list = joinWords(say, refs)
    if (q.key === 'show') q.text = t('do.showRef', { list })
    else if (refs.some((r) => r.startsWith('gen-'))) q.text = t('do.diffRef', { list })
    else q.text = refs.length === 1 ? t('do.diffAttempt', { list }) : t('do.diffAttempts', { list })
  }
  if (q.key === 'log') {
    const files = [...new Set(q.logs)]
    const known = files.filter((f) => ctx.logs[f])
    q.text = known.length > 1 ? t('do.logsN', { n: known.length }) : known.length ? t('do.logs') : t('do.read', { file: joinWords(say, files.map(basename)) })
    q.engines = known[0] ? ctx.logs[known[0]]?.engines ?? null : null
  }
  if (q.key === 'engine') {
    const n = loop || (masked.match(/position\s+(?:fen|startpos)/g) ?? []).length
    q.text = n > 1 ? t('do.engineOn', { n }) : t('do.engine')
  }
  if (q.key === 'match') {
    const runs = q.runs ?? []
    const first = runs[0]
    const games = first?.games ? tn('count.games', first.games) : t('do.someGames')
    const bg = runs.some((r) => r.bg)
    q.engines = first?.engines ?? null
    q.text = runs.length > 1
      ? t(bg ? 'do.matchesBg' : 'do.matches', { k: runs.length, games })
      : t(bg ? 'do.matchBg' : 'do.match', { games })
  }
}

export function describeBash(say: Say, command: string, ctx: Context): BashDesc {
  const { masked, bodies } = maskHeredocs(command)
  const loop = { n: 0 }
  // Command substitutions ($(date +%s)) are values, not commands.
  let flat = masked
  while (/\$\([^()]*\)/.test(flat)) flat = flat.replace(/\$\([^()]*\)/g, '$SUB')
  const parts = splitSegments(flat)
    .map(parseCommand)
    .map((s) => classify(say, s, ctx, bodies, loop))
    .filter((p): p is Part => p !== null)
  const merged = merge(parts)
  for (const q of merged) finish(say, q, ctx, masked, loop.n)
  // Reading the notes and writing them in one command is writing them.
  const written = new Set(merged.filter((q) => q.key.startsWith('note-write:')).map((q) => q.key.slice(11)))
  const seen = new Set<string>()
  let list = merged
    .filter((q) => !(q.key.startsWith('note:') && written.has(q.key.slice(5))))
    .filter((q) => q.text && !seen.has(q.text) && seen.add(q.text))
  if (!list.length) list = [{ cat: 'understand', key: 'cmd', text: say.t('do.command') }]
  const head = list[0]
  const cat: Cat = head?.cat === 'wait' ? 'wait'
    : list.some((q) => q.cat === 'try') ? 'try'
    : list.some((q) => q.cat === 'edit') ? 'edit'
    : list.some((q) => q.cat === 'deliver') ? 'deliver'
    : 'understand'
  let text = ''
  list.slice(0, 3).forEach((q, i) => {
    text += i === 0 ? q.text : (list[i - 1]?.key === 'sleep' ? say.t('do.then') : ', ') + q.text
  })
  const rest = list.length - 3
  if (rest > 0) text += rest === 1 ? say.t('do.oneMore') : say.t('do.more', { n: rest })
  const engines = list.find((q) => q.key === 'match' || (q.key === 'log' && q.engines))?.engines ?? null
  return { cat, text, wait: list.find((q) => q.key === 'sleep')?.wait ?? null, engines }
}
