/**
 * Reading what the agent ran, without running anything: a bash command split into simple
 * commands, and the Python repr the ledger kept for tool arguments before they were stored as
 * JSON. Pure functions, tolerant of text cut halfway.
 */

/** Python's repr of a dict, read tolerantly: a cut string or container ends where the text ends. */
export function parsePyRepr(src: string): { value: unknown; cut: boolean } {
  let cut = false
  if (src.length > 2000 && src.endsWith('...')) {
    src = src.slice(0, -3)
    cut = true
  }
  let i = 0
  const ws = () => {
    while (i < src.length && /\s/.test(src[i] ?? '')) i++
  }
  const str = (): string => {
    const quote = src[i++]
    let out = ''
    while (i < src.length) {
      const c = src[i++]
      if (c === '\\') {
        const n = src[i++]
        if (n === undefined) break
        out += n === 'n' ? '\n' : n === 't' ? '\t' : n === 'r' ? '\r' : n === '\\' || n === "'" || n === '"' ? n : `\\${n}`
      } else if (c === quote) return out
      else out += c
    }
    cut = true
    return out
  }
  const value = (): unknown => {
    ws()
    const c = src[i]
    if (c === '{' || c === '[') {
      const dict = c === '{'
      const close = dict ? '}' : ']'
      const obj: Record<string, unknown> = {}
      const list: unknown[] = []
      i++
      for (;;) {
        ws()
        if (i >= src.length) {
          cut = true
          return dict ? obj : list
        }
        if (src[i] === close) {
          i++
          return dict ? obj : list
        }
        if (dict) {
          const key = value()
          ws()
          if (src[i] !== ':') {
            cut = true
            return obj
          }
          i++
          obj[String(key)] = value()
        } else list.push(value())
        ws()
        if (src[i] === ',') i++
      }
    }
    if (c === "'" || c === '"') return str()
    const m = /^(-?\d+(?:\.\d+)?|True|False|None)/.exec(src.slice(i))
    if (m) {
      i += m[0].length
      return m[0] === 'True' ? true : m[0] === 'False' ? false : m[0] === 'None' ? null : Number(m[0])
    }
    cut = true
    i = src.length
    return null
  }
  try {
    return { value: value(), cut }
  } catch {
    return { value: null, cut: true }
  }
}

/** Heredoc bodies are taken out first, so a script never reads as shell. */
export function maskHeredocs(cmd: string): { masked: string; bodies: string[] } {
  const bodies: string[] = []
  const masked = cmd.replace(/<<-?\s*(['"]?)(\w+)\1[^\n]*\n([\s\S]*?)\n\2(?=\s|$)/g, (_m, _q, _tag, body: string) => {
    bodies.push(body)
    return `<<HEREDOC${bodies.length - 1}`
  })
  return { masked, bodies }
}

export type Segment = { text: string; piped: boolean; bg: boolean }

/** Simple commands, split on && || ; | & and newlines outside quotes. */
export function splitSegments(s: string): Segment[] {
  const out: Segment[] = []
  let cur = ''
  let quote: string | null = null
  let piped = false
  const push = (sep: 'and' | 'bg' | 'pipe' | 'seq' | 'end') => {
    if (cur.trim()) out.push({ text: cur.trim(), piped, bg: sep === 'bg' })
    piped = sep === 'pipe'
    cur = ''
  }
  for (let i = 0; i < s.length; i++) {
    const c = s[i] ?? ''
    if (quote) {
      cur += c
      if (c === '\\' && quote === '"') {
        cur += s[++i] ?? ''
        continue
      }
      if (c === quote) quote = null
      continue
    }
    if (c === "'" || c === '"') {
      quote = c
      cur += c
      continue
    }
    if (c === '\\') {
      cur += c + (s[i + 1] ?? '')
      i++
      continue
    }
    const two = s.slice(i, i + 2)
    if (two === '&&' || two === '||') {
      push('and')
      i++
      continue
    }
    if (c === '&' && (s[i + 1] === '>' || s[i - 1] === '>')) {
      cur += c
      continue
    }
    if (c === '&') push('bg')
    else if (c === '|') push('pipe')
    else if (c === ';' || c === '\n') push('seq')
    else if (c === '(' || c === ')') cur += s[i - 1] === '$' ? c : ' '
    else cur += c
  }
  push('end')
  return out
}

/** The words of a simple command, quotes removed. */
export function shellWords(seg: string): string[] {
  const words: string[] = []
  let cur = ''
  let quote: string | null = null
  let any = false
  for (let i = 0; i < seg.length; i++) {
    const c = seg[i] ?? ''
    if (quote) {
      if (c === quote) quote = null
      else if (c === '\\' && quote === '"' && i + 1 < seg.length) cur += seg[++i]
      else cur += c
      continue
    }
    if (c === "'" || c === '"') {
      quote = c
      any = true
    } else if (c === '\\' && i + 1 < seg.length) {
      cur += seg[++i]
      any = true
    } else if (/\s/.test(c)) {
      if (cur || any) {
        words.push(cur)
        cur = ''
        any = false
      }
    } else cur += c
  }
  if (cur || any) words.push(cur)
  return words
}

export type Command = { cmd: string; args: string[]; out: string | null; bg: boolean; piped: boolean; raw: string }

/** A simple command: its name and arguments, where its output goes, wrappers dropped. */
export function parseCommand(seg: Segment): Command {
  const words = shellWords(seg.text)
  const args: string[] = []
  let out: string | null = null
  for (let i = 0; i < words.length; i++) {
    const x = words[i] ?? ''
    if (x === '>' || x === '>>' || x === '1>' || x === '&>') {
      out = words[i + 1] ?? null
      i++
      continue
    }
    if (x === '2>' || x === '<') {
      i++
      continue
    }
    const m = /^(\d?|&)>>?(.+)$/.exec(x)
    if (m) {
      if (!m[2]?.startsWith('&') && m[1] !== '2') out = m[2] ?? null
      continue
    }
    args.push(x)
  }
  const wrapper = (w: string) =>
    ['nohup', 'time', 'exec', 'timeout'].includes(w) || (/^\d+[smh]?$/.test(w) && args.length > 1) || /^\w+=/.test(w)
  while (args.length && wrapper(args[0] ?? '')) args.shift()
  return { cmd: args[0] ?? '', args: args.slice(1), out, bg: seg.bg, piped: seg.piped, raw: seg.text }
}

export const basename = (path: unknown) => String(path ?? '').replace(/\/+$/, '').split('/').pop() ?? ''
