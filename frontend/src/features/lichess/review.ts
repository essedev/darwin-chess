import type { I18n } from '@/i18n/context'
import type { Judgement } from '@/lib/api'

/** The marks Lichess and chess books put after a move. */
export const MARK: Record<Judgement, string> = { blunder: '??', mistake: '?', inaccuracy: '?!' }

/** Text colour of each judgement: red, amber, blue, from the site's tokens. */
export const MARK_TONE: Record<Judgement, string> = {
  blunder: 'text-bad',
  mistake: 'text-c-spend',
  inaccuracy: 'text-c-strength',
}

/** Fill of each judgement's dot on the evaluation curve. */
export const MARK_FILL: Record<Judgement, string> = {
  blunder: 'fill-bad',
  mistake: 'fill-c-spend',
  inaccuracy: 'fill-c-strength',
}

export const JUDGEMENTS: readonly Judgement[] = ['inaccuracy', 'mistake', 'blunder']

// referee/analysis.py writes a forced mate as ±10000, without the distance.
const MATE = 10000

/** An evaluation from the bot's side in pawns: "+0,4", "−3,1", "+M" for a forced mate. */
export function pawns(i18n: I18n, cp: number): string {
  if (Math.abs(cp) >= MATE) return cp > 0 ? '+M' : '−M'
  const tenths = Math.round(cp / 10)
  const value = new Intl.NumberFormat(i18n.f.locale, { minimumFractionDigits: 1 }).format(Math.abs(tenths) / 10)
  return tenths > 0 ? `+${value}` : tenths < 0 ? `−${value}` : value
}

/** The number of a move by its index from the start: "12." for White, "12…" for Black. */
export function moveNumber(ply: number): string {
  const n = Math.floor(ply / 2) + 1
  return ply % 2 === 0 ? `${n}.` : `${n}…`
}
