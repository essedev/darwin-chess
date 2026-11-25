import type { Generation, Phase } from '@/lib/api'
import type { I18n } from '@/i18n/context'

export const PHASES: readonly (Phase | 'world')[] = ['genesis', 'first_steps', 'evolution', 'world']

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

/** Why a gate failed, in plain words, from its public detail ("problem" plus context). */
export function failureText(i18n: I18n, detail: Record<string, unknown>, gate?: string): string {
  const problem = String(detail.problem ?? '')
  if (gate === 'build' && problem === 'timeout') return i18n.t('failure.build_timeout')
  if (problem === 'wrong_count') return i18n.t('failure.wrong_count', { move: String(detail.move ?? '') })
  return i18n.label('failure', problem)
}

/** Who an arena engine is: the candidate, a champion, Stockfish. */
export function playerName(i18n: I18n, engine: string, candidate: number | undefined, champion: number): string {
  const { t } = i18n
  if (engine === 'candidate') return t('player.candidate', { id: candidate ?? '' })
  if (engine === 'champion') return t('player.champion', { gen: champion })
  if (engine === 'random') return t('player.random')
  const gen = /^gen-(\d+)$/.exec(engine)
  if (gen) return t('player.champion', { gen: gen[1] ?? '' })
  const stockfish = /^stockfish-(\d+)$/.exec(engine)
  if (stockfish) return t('player.stockfish', { level: stockfish[1] ?? '' })
  return engine
}

/**
 * What kind of game the arena is playing, from the two engine names: the kind ("Giudizio")
 * and who plays ("candidato #6 contro il campione gen-2"); null for an unknown pairing.
 */
export function matchLabel(
  i18n: I18n,
  white: string,
  black: string,
  candidate: number | undefined,
  champion: number,
): { kind: string; players: string } | null {
  const { t } = i18n
  const engines = [white, black]
  const id = candidate ?? ''
  if (engines.includes('candidate')) {
    const other = engines.find((e) => e !== 'candidate')
    if (other === 'random') return { kind: t('arena.kind.judging'), players: t('arena.vsRandom', { id }) }
    if (other === 'champion') return { kind: t('arena.kind.judging'), players: t('arena.vsChampion', { id, gen: champion }) }
  }
  const gen = engines.map((e) => /^gen-(\d+)$/.exec(e)).find(Boolean)
  const stockfish = engines.map((e) => /^stockfish-(\d+)$/.exec(e)).find(Boolean)
  if (gen && stockfish) {
    return { kind: t('arena.kind.rating'), players: t('arena.vsStockfish', { gen: gen[1] ?? '', level: stockfish[1] ?? '' }) }
  }
  return null
}

/** "2 h 14 min", "38 min", "meno di un minuto". */
export function duration(i18n: I18n, ms: number): string {
  const minutes = Math.floor(Math.max(0, ms) / 60000)
  if (minutes < 1) return i18n.t('duration.underMinute')
  const hours = Math.floor(minutes / 60)
  return hours > 0 ? i18n.t('duration.hours', { h: hours, m: minutes % 60 }) : i18n.t('duration.minutes', { m: minutes })
}

/** A chess clock: "2:58". */
export function clock(ms: number): string {
  const seconds = Math.ceil(Math.max(0, ms) / 1000)
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`
}

/** The colour of a game result; its words are in the dictionaries under `result.*`. */
export const RESULT_TONE: Record<string, string> = {
  win: 'text-good',
  draw: 'text-muted-foreground',
  loss: 'text-bad',
  aborted: 'text-muted-foreground',
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
