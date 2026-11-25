import { ChevronDown } from 'lucide-react'
import { dateTime } from '@/features/live/format'
import { useGenerationsDetail } from '@/lib/api'
import { href } from '@/lib/use-route'

/** Which version of the code is on screen: the champion, a past generation, or one attempt. */
export function RefSelect(props: { current: string | undefined; commit: string; generation: number | null; path: string | null }) {
  const generations = useGenerationsDetail()
  const list = generations.data ?? []
  const champion = list[0]?.id
  const current = props.current ?? ''
  const known = current === '' || list.some((g) => `gen-${g.id}` === current)
  // What changed in the version on screen: the ref itself, or the champion's generation.
  const shownRef = current || (props.generation !== null ? `gen-${props.generation}` : '')
  const diffable = /^(gen-[1-9]\d*|exp-\d+)$/.test(shownRef) ? shownRef : null
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
      <label className="relative inline-flex items-center">
        <span className="sr-only">Versione del codice</span>
        <select
          value={current}
          onChange={(event) => {
            window.location.hash = href('codice', { ref: event.target.value, path: props.path })
          }}
          className="h-9 cursor-pointer appearance-none rounded-full bg-card pr-9 pl-4 text-[14px] font-medium shadow-[inset_0_0_0_1px_var(--border)] focus-visible:ring-2 focus-visible:ring-ring/60 focus-visible:outline-none"
        >
          <option value="">Campione attuale{champion !== undefined ? ` (gen-${champion})` : ''}</option>
          {!known && <option value={current}>{refLabel(current)}</option>}
          {list.map((g) => (
            <option key={g.id} value={`gen-${g.id}`}>
              gen-{g.id} · {dateTime(g.created_at)}
            </option>
          ))}
        </select>
        <ChevronDown aria-hidden className="pointer-events-none absolute right-3 size-4 text-muted-foreground" />
      </label>
      <span className="font-mono text-[12px] text-muted-foreground" title={props.commit}>
        commit {props.commit.slice(0, 7)}
      </span>
      {diffable && (
        <a href={href('codice', { diff: diffable })} className="cursor-pointer text-[13px] font-medium text-live underline-offset-4 hover:underline">
          Cosa è cambiato qui
        </a>
      )}
    </div>
  )
}

function refLabel(ref: string): string {
  const exp = /^exp-(\d+)$/.exec(ref)
  if (exp) return `Tentativo #${exp[1]}`
  return /^[0-9a-f]{7,40}$/.test(ref) ? `commit ${ref.slice(0, 7)}` : ref
}
