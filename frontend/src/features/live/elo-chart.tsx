import { useLayoutEffect, useRef, useState } from 'react'
import { useI18n } from '@/i18n/context'
import { type EloPoint, overlap } from './format'

/**
 * Each generation as a point with its error bar, the shared band behind them, a dashed line
 * between the central values. Drawn at the width it gets, so the labels keep their size.
 */
export function EloChart({ points, height = 110, axis = false }: { points: EloPoint[]; height?: number; axis?: boolean }) {
  const { t, f } = useI18n()
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

  const band = overlap(points)
  const lows = points.map((p) => p.elo - p.error)
  const highs = points.map((p) => p.elo + p.error)
  const low = Math.floor((Math.min(...lows) - 30) / 100) * 100
  const high = Math.ceil((Math.max(...highs) + 30) / 100) * 100
  const left = axis ? 40 : 6
  const right = 8
  const top = 8
  const bottom = 22
  const x = (i: number) => left + ((width - left - right) * (i + 0.5)) / points.length
  const y = (elo: number) => top + (height - top - bottom) * (1 - (elo - low) / Math.max(1, high - low))
  const ticks = axis ? gridTicks(low, high) : []

  return (
    <div ref={box} className="w-full">
      {width > 0 && points.length > 0 && (
        <svg width={width} height={height} role="img" aria-label={t('elo.chartLabel')} className="block overflow-visible">
          {ticks.map((v) => (
            <g key={v}>
              <line x1={left} x2={width - right} y1={y(v)} y2={y(v)} className="stroke-border" />
              <text x={left - 6} y={y(v) + 3} textAnchor="end" className="fill-muted-foreground font-mono text-[10px]">
                {f.num(v)}
              </text>
            </g>
          ))}
          {band && (
            <rect x={left} width={width - left - right} y={y(band[1])} height={y(band[0]) - y(band[1])} rx={3}
                  className="fill-[var(--hue,var(--live))] opacity-10" />
          )}
          {points.length > 1 && (
            <path d={points.map((p, i) => `${i ? 'L' : 'M'}${x(i)},${y(p.elo)}`).join(' ')}
                  className="fill-none stroke-[var(--hue,var(--live))] opacity-70" strokeWidth={1.5} strokeDasharray="3 3" />
          )}
          {points.map((p, i) => (
            <g key={p.id} className="stroke-[var(--hue,var(--live))]">
              <line x1={x(i)} x2={x(i)} y1={y(p.elo + p.error)} y2={y(p.elo - p.error)} strokeWidth={1.5} opacity={0.55} />
              <line x1={x(i) - 5} x2={x(i) + 5} y1={y(p.elo + p.error)} y2={y(p.elo + p.error)} strokeWidth={1.5} opacity={0.55} />
              <line x1={x(i) - 5} x2={x(i) + 5} y1={y(p.elo - p.error)} y2={y(p.elo - p.error)} strokeWidth={1.5} opacity={0.55} />
              <circle cx={x(i)} cy={y(p.elo)} r={4} className="fill-[var(--hue,var(--live))] stroke-none">
                <title>{`gen-${p.id}: ${f.num(Math.round(p.elo))} ± ${f.num(Math.round(p.error))}`}</title>
              </circle>
              <text x={x(i)} y={height - 6} textAnchor="middle" className="fill-muted-foreground stroke-none font-mono text-[10px]">
                gen-{p.id}
              </text>
            </g>
          ))}
        </svg>
      )}
    </div>
  )
}

/** Gridlines every 100 Elo, or every 200 when the range is wide. */
function gridTicks(low: number, high: number): number[] {
  const step = high - low > 600 ? 200 : 100
  const ticks = []
  for (let v = Math.ceil(low / step) * step; v <= high; v += step) ticks.push(v)
  return ticks
}
