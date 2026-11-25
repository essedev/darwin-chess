import { useEffect, useState } from 'react'
import { cn } from '@/lib/utils'

/**
 * Small ASCII animations for the states of the site (concept C, variant E): a knight hopping
 * in L-shapes while data loads, a king shaking when the API is down, the pieces walking to
 * their squares when there is nothing yet. Every character takes one of the subject colours,
 * drifting slowly. Decorative: hidden from screen readers, the text next to it says the state.
 */
export type Art = 'loading' | 'error' | 'empty' | 'inline'

const TICK_MS = 125
const COLOURS = ['var(--c-strength)', 'var(--c-gens)', 'var(--live)', 'var(--c-verdict)', 'var(--c-spend)']

// A knight's walk on a 6x6 board, each step an L.
const TOUR: [number, number][] = [
  [0, 0], [1, 2], [0, 4], [2, 5], [4, 4], [5, 2], [4, 0], [2, 1],
  [3, 3], [1, 4], [3, 5], [5, 4], [4, 2], [5, 0], [3, 1], [1, 0],
]

function knight(t: number): string {
  const k = t % TOUR.length
  const at = (step: number) => TOUR[(k - step + TOUR.length) % TOUR.length]
  const rows: string[] = []
  for (let y = 0; y < 6; y++) {
    let line = ''
    for (let x = 0; x < 6; x++) {
      const trail = [1, 2, 3].find((d) => at(d)?.[0] === x && at(d)?.[1] === y)
      const here = TOUR[k]?.[0] === x && TOUR[k]?.[1] === y
      line += here ? ' ♞' : trail === 1 ? ' •' : trail ? ' ∘' : (x + y) % 2 ? ' ·' : '  '
    }
    rows.push(line)
  }
  return rows.join('\n')
}

function setup(t: number): string {
  const back = '♜♞♝♛♚♝♞♜'
  const shown = Math.min(16, Math.floor(t / 2) % 24)
  const rank8 = [...back].map((p, i) => (i < shown ? p : '·')).join(' ')
  const rank7 = Array.from({ length: 8 }, (_, i) => (i + 8 < shown ? '♟' : '·')).join(' ')
  return [rank8, rank7, '· · · · · · · ·', '· · · · · · · ·'].join('\n')
}

const FRAMES: Record<Art, (t: number) => string> = {
  loading: knight,
  error: () => '♚',
  empty: setup,
  inline: (t) => Array.from({ length: 6 }, (_, i) => (i === t % 6 ? '♞' : '·')).join(' '),
}

function useTick(still: boolean): number {
  const [t, setT] = useState(0)
  useEffect(() => {
    if (still) return
    const id = window.setInterval(() => setT((n) => n + 1), TICK_MS)
    return () => window.clearInterval(id)
  }, [still])
  return t
}

const prefersStill = () => typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches

export function AsciiArt({ art, className }: { art: Art; className?: string }) {
  const [still] = useState(prefersStill)
  const t = useTick(still)
  const frame = FRAMES[art](still ? 6 : t)
  return (
    <pre
      aria-hidden
      className={cn(
        'm-0 font-mono leading-[1.15] whitespace-pre select-none',
        art === 'error' ? 'text-[56px] leading-none' : art === 'inline' ? 'text-[12.5px]' : 'text-[15px]',
        art === 'error' && !still && 'animate-[king-shake_1.2s_infinite]',
        className,
      )}
    >
      {frame.split('\n').map((line, y) => (
        <span key={y}>
          {[...line].map((ch, x) =>
            ch === ' ' ? ' ' : (
              <span key={x} style={{ color: ch === '♞' || ch === '♚' ? 'var(--live)' : COLOURS[(x + y * 2 + Math.floor(t / 3)) % COLOURS.length] }}>
                {ch}
              </span>
            ),
          )}
          {y < frame.split('\n').length - 1 ? '\n' : ''}
        </span>
      ))}
    </pre>
  )
}
