import { type PointerEvent, useId, useLayoutEffect, useRef, useState } from 'react'
import { useT } from '@/i18n/context'
import type { Judgement } from '@/lib/api'
import { MARK_FILL } from './review'

/**
 * The bot's winning chances over a game (-100 to 100, one per position): a line with the
 * area between it and zero, green where the bot is ahead and red where it is behind.
 */
function Area({ values, x, y, clipId, width, height }: {
  values: number[]
  x: (i: number) => number
  y: (v: number) => number
  clipId: string
  width: number
  height: number
}) {
  const line = values.map((v, i) => `${i ? 'L' : 'M'}${x(i)},${y(v)}`).join(' ')
  const last = values.length - 1
  const area = `${line} L${x(last)},${y(0)} L${x(0)},${y(0)} Z`
  return (
    <>
      <defs>
        <clipPath id={`${clipId}-up`}><rect x={0} y={0} width={width} height={y(0)} /></clipPath>
        <clipPath id={`${clipId}-down`}><rect x={0} y={y(0)} width={width} height={height - y(0)} /></clipPath>
      </defs>
      <path d={area} clipPath={`url(#${clipId}-up)`} className="fill-good opacity-20" />
      <path d={area} clipPath={`url(#${clipId}-down)`} className="fill-bad opacity-20" />
      <line x1={x(0)} x2={x(last)} y1={y(0)} y2={y(0)} className="stroke-border" />
      <path d={line} className="fill-none stroke-foreground" strokeWidth={1.25} strokeLinejoin="round" />
    </>
  )
}

/** The width of a box, followed as it resizes: the charts draw at the size they get. */
function useWidth() {
  const box = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(0)
  useLayoutEffect(() => {
    const el = box.current
    if (!el) return
    const measure = () => setWidth(el.clientWidth)
    measure()
    const observer = new ResizeObserver(measure)
    observer.observe(el)
    return () => observer.disconnect()
  }, [])
  return { box, width }
}

/**
 * The evaluation of a whole game: the curve, a dot on every judged move (on the position it
 * led to), a cursor on the position on the board. Pointing or tapping picks a position.
 */
export function EvalChart(props: {
  chances: number[]
  judgements: (Judgement | null)[]
  current: number
  onSelect: (position: number) => void
  height?: number
}) {
  const t = useT()
  const clipId = useId().replaceAll(':', '')
  const { box, width } = useWidth()
  const height = props.height ?? 150
  const pad = 6
  const n = props.chances.length
  const x = (i: number) => pad + ((width - 2 * pad) * i) / Math.max(1, n - 1)
  const y = (v: number) => pad + ((height - 2 * pad) * (100 - v)) / 200
  const pick = (event: PointerEvent<SVGSVGElement>) => {
    const left = event.currentTarget.getBoundingClientRect().left
    const i = Math.round(((event.clientX - left - pad) / Math.max(1, width - 2 * pad)) * (n - 1))
    props.onSelect(Math.max(0, Math.min(n - 1, i)))
  }
  return (
    <div ref={box} className="w-full">
      {width > 0 && n > 1 && (
        <svg
          width={width}
          height={height}
          role="img"
          aria-label={t('game.chart.label')}
          onPointerDown={pick}
          onPointerMove={(event) => event.buttons === 1 && pick(event)}
          className="block cursor-pointer touch-none select-none"
        >
          <Area values={props.chances} x={x} y={y} clipId={clipId} width={width} height={height} />
          <text x={pad + 2} y={pad + 10} className="fill-muted-foreground font-sans text-[10px]">{t('game.chart.ahead')}</text>
          <text x={pad + 2} y={height - pad - 3} className="fill-muted-foreground font-sans text-[10px]">{t('game.chart.behind')}</text>
          <line x1={x(props.current)} x2={x(props.current)} y1={0} y2={height} className="stroke-live" strokeWidth={1.5} />
          {props.judgements.map((judgement, ply) =>
            judgement && ply + 1 < n ? (
              <circle key={ply} cx={x(ply + 1)} cy={y(props.chances[ply + 1] ?? 0)} r={judgement === 'inaccuracy' ? 2.5 : 3.5}
                      className={`${MARK_FILL[judgement]} stroke-card`} strokeWidth={1} />
            ) : null,
          )}
          <circle cx={x(props.current)} cy={y(props.chances[props.current] ?? 0)} r={4} className="fill-live stroke-card" strokeWidth={1.5} />
        </svg>
      )}
    </div>
  )
}

/** The same curve in small, for a row of the list: the shape of the game at a glance. */
export function Spark({ values, label }: { values: number[]; label: string }) {
  const clipId = useId().replaceAll(':', '')
  const width = 72
  const height = 24
  const x = (i: number) => (width * i) / Math.max(1, values.length - 1)
  const y = (v: number) => 1 + ((height - 2) * (100 - v)) / 200
  return (
    <svg width={width} height={height} role="img" aria-label={label} className="block flex-none">
      <Area values={values} x={x} y={y} clipId={clipId} width={width} height={height} />
    </svg>
  )
}
