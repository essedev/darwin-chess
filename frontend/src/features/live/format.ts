import type { Generation, Phase } from '@/lib/api'

export const PHASES: { key: Phase | 'world'; name: string; goal: string }[] = [
  { key: 'genesis', name: 'Genesi', goal: 'imparare le regole' },
  { key: 'first_steps', name: 'Primi passi', goal: 'battere il giocatore casuale' },
  { key: 'evolution', name: 'Evoluzione', goal: 'battere il campione' },
  { key: 'world', name: 'Mondo', goal: 'giocare su Lichess' },
]

const euro = new Intl.NumberFormat('it-IT', { style: 'currency', currency: 'USD' })
const decimal = new Intl.NumberFormat('it-IT', { maximumFractionDigits: 2 })

export const money = (usd: number) => euro.format(usd)
export const num = (value: number) => decimal.format(value)

/**
 * Elo per champion. Absolute (against Stockfish anchors) once a champion has been rated;
 * before that, relative to the random player: the sum of every promotion's gain.
 */
export function eloSeries(generations: Generation[]): { absolute: boolean; points: { id: number; elo: number }[] } {
  const rated = generations.filter((g) => g.elo_absolute !== null)
  if (rated.length > 0) {
    return { absolute: true, points: rated.map((g) => ({ id: g.id, elo: Math.round(g.elo_absolute ?? 0) })) }
  }
  let total = 0
  const points = generations
    .filter((g) => g.id >= 1)
    .map((g) => {
      total += g.elo_vs_parent ?? 0
      return { id: g.id, elo: Math.round(total) }
    })
  return { absolute: false, points }
}

export const STATUS: Record<string, string> = {
  running: 'al lavoro',
  judging: 'in giudizio',
  accepted: 'promosso',
  rejected: 'scartato',
  abandoned: 'nessuna consegna',
  stale: 'superato da un campione nuovo',
  error: 'errore',
  budget_stop: 'fermato dal tetto di spesa',
  reflected: 'riflessione',
}

export const GATES: Record<string, string> = {
  build: 'compila',
  perft: 'regole',
  smoke: 'partite pulite',
  match: 'match',
}

export const TOOLS: Record<string, string> = {
  read: 'legge',
  write: 'scrive',
  edit: 'modifica',
  bash: 'terminale',
  perft_check: 'verifica le regole',
  submit: 'consegna',
  experiments: 'rilegge gli esperimenti',
  run_job: 'lavoro lungo',
}

/** Who an arena engine is, in plain Italian: the candidate, a champion, Stockfish. */
export function playerName(engine: string, candidate: number | undefined, champion: number): string {
  if (engine === 'candidate') return `Candidato #${candidate ?? ''}`
  if (engine === 'champion') return `Campione gen-${champion}`
  if (engine === 'random') return 'Giocatore casuale'
  const gen = /^gen-(\d+)$/.exec(engine)
  if (gen) return `Campione gen-${gen[1]}`
  const stockfish = /^stockfish-(\d+)$/.exec(engine)
  if (stockfish) return `Stockfish ${stockfish[1]}`
  return engine
}

/**
 * What kind of game the arena is playing, from the two engine names: the kind ("Giudizio")
 * and who plays ("candidato #6 contro il campione gen-2"); null for an unknown pairing.
 */
export function matchLabel(
  white: string,
  black: string,
  candidate: number | undefined,
  champion: number,
): { kind: string; players: string } | null {
  const engines = [white, black]
  const id = candidate ?? ''
  if (engines.includes('candidate')) {
    const other = engines.find((e) => e !== 'candidate')
    if (other === 'random') return { kind: 'Giudizio', players: `candidato #${id} contro il giocatore casuale` }
    if (other === 'champion') return { kind: 'Giudizio', players: `candidato #${id} contro il campione gen-${champion}` }
  }
  const gen = engines.map((e) => /^gen-(\d+)$/.exec(e)).find(Boolean)
  const stockfish = engines.map((e) => /^stockfish-(\d+)$/.exec(e)).find(Boolean)
  if (gen && stockfish) return { kind: 'Misura dell’Elo', players: `gen-${gen[1]} contro Stockfish ${stockfish[1]}` }
  return null
}

/** "2 h 14 min", "38 min", "meno di un minuto". */
export function duration(ms: number): string {
  const minutes = Math.floor(Math.max(0, ms) / 60000)
  if (minutes < 1) return 'meno di un minuto'
  const hours = Math.floor(minutes / 60)
  return hours > 0 ? `${hours} h ${minutes % 60} min` : `${minutes} min`
}

/** A chess clock: "2:58". */
export function clock(ms: number): string {
  const seconds = Math.ceil(Math.max(0, ms) / 1000)
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`
}

export const RESULTS: Record<string, { label: string; tone: string }> = {
  win: { label: 'Vinta', tone: 'text-good' },
  draw: { label: 'Patta', tone: 'text-muted-foreground' },
  loss: { label: 'Persa', tone: 'text-bad' },
  aborted: { label: 'Annullata', tone: 'text-muted-foreground' },
}

/** The agent writes Markdown; the caption shows plain text on one paragraph. */
export function plainText(markdown: string): string {
  return markdown
    .replace(/```[\s\S]*?```/g, ' ')
    .replace(/\*\*|__|`/g, '') // emphasis and code marks; single underscores are names
    .replace(/^\s*(#+|>)\s*/gm, '')
    .replace(/^\s*[-+]\s+/gm, '')
    .replace(/\s+/g, ' ')
    .trim()
}
