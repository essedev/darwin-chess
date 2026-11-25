import type { Job, Jobs } from '@/lib/api'
import { cn } from '@/lib/utils'
import { useNow } from '@/lib/use-now'
import { duration } from './format'

const card = 'rounded-[18px] bg-card p-5 shadow-[inset_0_0_0_1px_var(--border)]'
const RECENT_MS = 24 * 60 * 60 * 1000

/**
 * A long CPU job the agent started (self-play, tuning): shown while one runs, or for a day
 * after the last one ended. What the job does inside is the agent's own code: only the
 * command, the time and the outcome are known here.
 */
export function JobCard({ jobs }: { jobs: Jobs }) {
  const running = jobs.running.length > 0
  const now = useNow(30000)
  const last = jobs.last_finished
  const ended = last?.finished_at ? Date.parse(last.finished_at) : null
  if (!running && (last === null || ended === null || now - ended > RECENT_MS)) return null
  return (
    <section className={card}>
      <p className="mb-2.5 text-[13px] text-muted-foreground">Lavoro lungo</p>
      {running ? (
        <ul className="grid gap-3">
          {jobs.running.map((job) => (
            <li key={job.id} className="min-w-0">
              <Command job={job} />
              <p className="mt-1.5 text-xs text-muted-foreground">
                <span className="font-semibold text-live">in corso</span> da {duration(now - Date.parse(job.created_at))} · al massimo{' '}
                {hours(job.max_hours)}
              </p>
            </li>
          ))}
        </ul>
      ) : (
        last && ended !== null && (
          <>
            <Command job={last} />
            <p className="mt-1.5 text-xs text-muted-foreground">
              <span className={cn('font-semibold', last.status === 'done' ? 'text-good' : 'text-bad')}>{outcome(last)}</span>{' '}
              dopo {duration(ended - Date.parse(last.created_at))}
            </p>
          </>
        )
      )}
    </section>
  )
}

function Command({ job }: { job: Job }) {
  return (
    <code className="block truncate rounded-md bg-muted px-2 py-1.5 font-mono text-xs" title={job.command}>
      {job.command}
    </code>
  )
}

function hours(value: number) {
  return value === 1 ? '1 ora' : `${String(value).replace('.', ',')} ore`
}

function outcome(job: NonNullable<Jobs['last_finished']>) {
  if (job.status === 'done') return 'finito'
  if (job.status === 'killed') return 'interrotto'
  if (job.status === 'failed') return job.exit_code === null ? 'fallito' : `fallito (codice ${job.exit_code})`
  return job.status
}
