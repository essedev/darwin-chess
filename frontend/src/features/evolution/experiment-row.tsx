import { GATES, STATUS, dateTime, failureText, num, preciseMoney, plainText, signed } from '@/features/live/format'
import type { ExperimentRow as Experiment } from '@/lib/api'
import { href } from '@/lib/use-route'
import { cn } from '@/lib/utils'

const TONE: Record<string, string> = {
  accepted: 'text-good',
  rejected: 'text-bad',
  error: 'text-bad',
  abandoned: 'text-bad',
  budget_stop: 'text-bad',
  running: 'text-live',
  judging: 'text-live',
}

export function ExperimentRow({ experiment: e }: { experiment: Experiment }) {
  const reflection = e.kind === 'reflection'
  const text = e.hypothesis
    ? plainText(e.hypothesis)
    : reflection
      ? 'L’agente rilegge i suoi esperimenti e aggiorna strategia e appunti.'
      : 'Nessuna ipotesi registrata.'
  const reason = rejection(e)
  return (
    <li
      className={cn(
        'grid gap-1.5 rounded-[14px] px-4 py-3.5',
        reflection ? 'border border-dashed' : 'bg-card shadow-[inset_0_0_0_1px_var(--border)]',
      )}
    >
      <p className="flex flex-wrap items-baseline gap-x-2.5 gap-y-0.5 text-[12px]">
        <span className="font-mono text-[13px] font-medium">#{e.id}</span>
        {reflection ? (
          <span className="rounded-full bg-muted px-2 py-px font-medium text-muted-foreground">riflessione</span>
        ) : (
          <span className={cn('font-semibold', TONE[e.status] ?? 'text-muted-foreground')}>{STATUS[e.status] ?? e.status}</span>
        )}
        <time dateTime={e.created_at} className="text-muted-foreground">{dateTime(e.created_at)}</time>
        {e.cost_usd !== null && (
          <span className="ml-auto font-mono text-muted-foreground tabular-nums" title="Costo delle chiamate al modello">
            {preciseMoney(e.cost_usd)}
          </span>
        )}
      </p>
      <p className={cn('text-[14px] leading-snug text-pretty', reflection && 'text-muted-foreground italic')}>{text}</p>
      {reason && (
        <p className="text-[13px] leading-relaxed text-muted-foreground">
          <span className="font-medium text-bad">Fermato a «{reason.gate}»</span>
          {reason.why && `: ${reason.why}`}
        </p>
      )}
      {e.candidate_commit && (
        <a
          href={href('codice', { diff: `exp-${e.id}` })}
          className="w-fit cursor-pointer text-[13px] font-medium text-live underline-offset-4 hover:underline"
        >
          Vedi le modifiche
        </a>
      )}
    </li>
  )
}

/** Which gate stopped it and why, in plain words; null when it was not rejected. */
function rejection(e: Experiment): { gate: string; why: string } | null {
  if (!e.rejected_at_gate) return null
  const gate = GATES[e.rejected_at_gate] ?? e.rejected_at_gate
  const failed = e.gates.find((g) => g.gate === e.rejected_at_gate)
  if (e.rejected_at_gate === 'match' && e.match) {
    const m = e.match
    const games = m.wins + m.draws + m.losses
    const elo = m.elo === null ? '' : `${signed(m.elo)}${m.elo_error === null ? '' : ` ± ${num(Math.round(m.elo_error))}`} Elo `
    return { gate, why: `${elo}contro ${opponent(m.opponent)} in ${games} partite (${m.wins} vinte, ${m.draws} patte, ${m.losses} perse)` }
  }
  return { gate, why: failed ? failureText(failed.detail, failed.gate) : '' }
}

function opponent(name: string): string {
  if (name === 'random') return 'il giocatore casuale'
  if (name === 'champion') return 'il campione'
  const gen = /^gen-(\d+)$/.exec(name)
  return gen ? `il campione gen-${gen[1]}` : name
}
