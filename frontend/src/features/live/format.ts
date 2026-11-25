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

/** Elo over the random player: the sum of every promotion's gain. Absolute Elo needs M6. */
export function cumulativeElo(generations: Generation[]): { id: number; elo: number }[] {
  let total = 0
  return generations
    .filter((g) => g.id >= 1)
    .map((g) => {
      total += g.elo_vs_parent ?? 0
      return { id: g.id, elo: Math.round(total) }
    })
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
