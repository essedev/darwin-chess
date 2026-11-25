import type { Commentary, Phase } from '@/lib/api'
import { type I18n, type Lang, type Picked, pickText } from '@/i18n/context'

export const PHASES: readonly (Phase | 'world')[] = ['genesis', 'first_steps', 'evolution', 'world']

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
 * What kind of game the arena is playing, from the two engine names: the kind ("Judgement")
 * and who plays ("candidate #6 vs the champion gen-2"); null for an unknown pairing.
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
    .replace(/^\s*(#+\s+|>\s*)/gm, '') // a heading needs a space: "#14" is an experiment
    .replace(/^\s*[-+]\s+/gm, '')
    .replace(/\s+/g, ' ')
    .trim()
}

/**
 * An experiment's short title in the visitor's language. Until the title is written (it comes
 * a few seconds after a submission), the first sentence of the hypothesis stands in.
 */
export function titleText(
  lang: Lang,
  title: Commentary | null | undefined,
  hypothesis: { en: string | null | undefined; it: string | null | undefined },
): Picked | null {
  const own = pickText(lang, { it: title?.it, en: title?.en })
  if (own) return own
  const long = pickText(lang, hypothesis)
  if (!long) return null
  const text = plainText(long.text)
  return { ...long, text: /^(.+?[.;:])(\s|$)/.exec(text)?.[1]?.replace(/[.;:]$/, '') ?? text }
}

/** Lichess performance means little on a handful of games: below this it is not shown. */
export const MIN_PERFORMANCE_GAMES = 5

/** A generation's absolute Elo against Stockfish, with the 95% margin of the measure. */
export type EloPoint = { id: number; elo: number; error: number }

/**
 * Where every measure's margin overlaps, or null when two of them do not. While the band
 * exists the generations are not measurably different, whatever their central values say.
 */
export function overlap(points: EloPoint[]): [number, number] | null {
  if (points.length < 2) return null
  const low = Math.max(...points.map((p) => p.elo - p.error))
  const high = Math.min(...points.map((p) => p.elo + p.error))
  return low <= high ? [low, high] : null
}
