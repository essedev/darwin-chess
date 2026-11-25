import type { Experiment, Overview } from '@/lib/api'
import { cn } from '@/lib/utils'
import { GATES, money, num } from './format'
import { JobCard } from './job-card'

type Ready = Extract<Overview, { ready: true }>

const card = 'rounded-[18px] bg-card p-5 shadow-[inset_0_0_0_1px_var(--border)]'
const LLR_BOUND = 2.944

export function SideCards({ data }: { data: Ready }) {
  const shown = data.current?.status === 'running' || data.current?.status === 'judging'
    ? data.previous
    : data.current
  return (
    <aside className="order-2 grid min-w-0 content-start gap-3.5 lg:order-none">
      <VerdictCard experiment={shown} judging={data.current?.status === 'judging' ? data.current : null} />
      <JobCard jobs={data.jobs} />
      <SpendCard spend={data.spend} />
    </aside>
  )
}

function VerdictCard({ experiment, judging }: { experiment: Experiment | null; judging: Experiment | null }) {
  if (judging) {
    return (
      <section className={card}>
        <p className="mb-2.5 text-[13px] text-muted-foreground">Che cosa sta giudicando l’arbitro</p>
        <p className="mb-3.5 text-[22px] font-semibold tracking-tight">Candidato #{judging.id}</p>
        <p className="text-xs leading-relaxed text-muted-foreground">{judging.hypothesis}</p>
      </section>
    )
  }
  if (!experiment) {
    return (
      <section className={card}>
        <p className="mb-2.5 text-[13px] text-muted-foreground">Ultimo verdetto</p>
        <p className="text-[22px] font-semibold tracking-tight">Nessun esperimento ancora</p>
      </section>
    )
  }
  const match = experiment.match
  const accepted = experiment.status === 'accepted'
  const question = match
    ? match.opponent === 'random'
      ? 'Il candidato batte il giocatore casuale?'
      : 'Il candidato è più forte del campione?'
    : 'Il motore conosce le regole?'
  const failed = experiment.gates.find((g) => !g.passed)
  return (
    <section className={card}>
      <p className="mb-2.5 text-[13px] text-muted-foreground">{question}</p>
      <p className={cn('mb-3.5 text-[22px] font-semibold tracking-tight', accepted ? 'text-good' : 'text-bad')}>
        {accepted ? 'Sì: promosso' : failed ? `No: fermo a «${GATES[failed.gate] ?? failed.gate}»` : 'No'}
      </p>
      {match?.llr != null && <LlrBar llr={match.llr} />}
      {match && (
        <p className="mt-2.5 text-xs leading-relaxed text-muted-foreground">
          <span className="text-foreground">{match.wins + match.draws + match.losses}</span> partite ·{' '}
          <span className="text-foreground">{num(Math.round(match.elo ?? 0))}</span> Elo · V {match.wins} P {match.draws} S {match.losses}
        </p>
      )}
      {failed && !match && <FailureNote detail={failed.detail} />}
      <div className="mt-3 flex flex-wrap gap-3.5 text-xs text-muted-foreground">
        {experiment.gates.map((g) => (
          <span key={g.gate}>
            <span className={g.passed ? 'text-good' : 'text-bad'}>{g.passed ? '✓' : '✗'}</span> {GATES[g.gate] ?? g.gate}
          </span>
        ))}
      </div>
    </section>
  )
}

function LlrBar({ llr }: { llr: number }) {
  const share = Math.max(-1, Math.min(1, llr / LLR_BOUND))
  return (
    <div className="mt-3">
      <div className="relative h-2 rounded-full bg-muted">
        <span className="absolute top-0 left-1/2 h-2 w-px bg-border" />
        <span className={cn('absolute top-0 h-2 rounded-full', share >= 0 ? 'bg-good' : 'bg-bad')}
              style={{ left: `${share >= 0 ? 50 : 50 + share * 50}%`, width: `${Math.abs(share) * 50}%` }} />
      </div>
      <div className="mt-1.5 flex justify-between font-mono text-[11px] text-muted-foreground">
        <span>scarta</span><span>LLR {num(llr)}</span><span>accetta</span>
      </div>
    </div>
  )
}

function FailureNote({ detail }: { detail: Record<string, unknown> }) {
  const problem = String(detail.problem ?? '')
  const text: Record<string, string> = {
    wrong_count: `Sbaglia il conteggio delle mosse dopo ${String(detail.move ?? '')}.`,
    missing_moves: 'Non vede alcune mosse legali.',
    illegal_moves: 'Considera mosse illegali.',
    protocol: 'Non risponde ancora come un motore UCI.',
    build_failed: 'Il codice non compila.',
    illegal_move: 'Ha giocato una mossa illegale.',
    crash: 'Si è bloccato durante una partita.',
    timeout: 'Ha smesso di rispondere durante una partita.',
  }
  return <p className="mt-2.5 text-xs leading-relaxed text-muted-foreground">{text[problem] ?? problem}</p>
}

function SpendCard({ spend }: { spend: Ready['spend'] }) {
  const share = Math.min(1, spend.usd / spend.budget)
  const full = spend.usd >= spend.budget
  return (
    <section className={card}>
      <p className="mb-2.5 text-[13px] text-muted-foreground">Quanto abbiamo speso oggi?</p>
      <p className="flex items-baseline gap-2.5">
        <b className="text-[32px] leading-none font-semibold tracking-tight tabular-nums">{money(spend.usd)}</b>
        <span className="font-mono text-[13px] text-muted-foreground">di {money(spend.budget)}</span>
      </p>
      <div className="mt-3 h-1.5 rounded-full bg-muted">
        <i className={cn('block h-1.5 rounded-full', full ? 'bg-bad' : 'bg-live')} style={{ width: `${share * 100}%` }} />
      </div>
      <p className="mt-2.5 text-xs text-muted-foreground">
        {full ? 'Tetto raggiunto: l’agente riprende dopo mezzanotte (UTC).' : `${spend.sessions} sessioni oggi`}
      </p>
    </section>
  )
}
