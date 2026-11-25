/** Elo per generation, the line of the "Come sta andando" card. */
export function Spark({ points }: { points: { id: number; elo: number }[] }) {
  if (points.length < 2) return null
  const width = 300
  const height = 84
  const elos = points.map((p) => p.elo)
  const low = Math.min(0, ...elos)
  const high = Math.max(...elos, low + 1)
  const x = (i: number) => 4 + ((width - 8) * i) / (points.length - 1)
  const y = (elo: number) => 6 + (height - 12) * (1 - (elo - low) / (high - low))
  const line = points.map((p, i) => `${i === 0 ? 'M' : 'L'}${x(i)},${y(p.elo)}`).join(' ')
  const last = points.at(-1)
  if (!last) return null
  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="mt-3.5 block h-auto w-full overflow-visible" role="img" aria-label="Elo per generazione">
      <path d={`${line} L${x(points.length - 1)},${height} L${x(0)},${height} Z`} className="fill-live opacity-10" />
      <path d={line} className="fill-none stroke-live" strokeWidth={2} strokeLinejoin="round" />
      <circle cx={x(points.length - 1)} cy={y(last.elo)} r={3.5} className="fill-live" />
    </svg>
  )
}
