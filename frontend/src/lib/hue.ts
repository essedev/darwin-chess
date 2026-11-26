import type { CSSProperties } from 'react'

/** What a panel is about: each subject has its colour across the site (index.css, --c-*); what
    is happening now is coral (--live). */
export type Hue = 'strength' | 'gens' | 'verdict' | 'spend' | 'live'

const HUES: Record<Hue, string> = {
  strength: 'var(--c-strength)',
  gens: 'var(--c-gens)',
  verdict: 'var(--c-verdict)',
  spend: 'var(--c-spend)',
  live: 'var(--live)',
}

/** The CSS variable a hue sets: children read it as var(--hue) for their accents. */
export const hueStyle = (hue?: Hue): CSSProperties | undefined =>
  hue ? ({ '--hue': HUES[hue] } as CSSProperties) : undefined
