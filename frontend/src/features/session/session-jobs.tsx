import { card } from '@/components/page'
import { duration } from '@/features/live/format'
import { type I18n, useI18n } from '@/i18n/context'
import { LangBadge } from '@/i18n/parts'
import type { ReadJob, SessionJob } from '@/lib/api'
import { useNow } from '@/lib/use-now'
import { href } from '@/lib/use-route'
import { cn } from '@/lib/utils'

const link = 'cursor-pointer font-medium text-live underline-offset-4 hover:underline'
const command = 'rounded-md bg-muted px-2 py-1.5 font-mono text-xs whitespace-pre-wrap break-all'

/**
 * The long jobs a session started: what each was for, how it ended and, when it went wrong,
 * the line that says why. The command itself is a click away.
 */
export function SessionJobs({ jobs }: { jobs: SessionJob[] }) {
  const i18n = useI18n()
  const { t, lang } = i18n
  const now = useNow(30000, jobs.some((j) => j.status === 'running'))
  if (jobs.length === 0) return null
  return (
    <section aria-labelledby="session-jobs" className={cn(card, 'grid gap-3 text-[14px]')}>
      <h2 id="session-jobs" className="panel-label">{t('job.sessionTitle')}</h2>
      <ul className="grid divide-y">
        {jobs.map((job) => (
          <li key={job.id} className="grid min-w-0 gap-1.5 py-3 first:pt-0 last:pb-0">
            {job.purpose ? (
              <p className="font-medium text-pretty">
                <span lang="en">{job.purpose}</span>
                {lang !== 'en' && <LangBadge lang="en" className="ml-1.5" />}
              </p>
            ) : (
              <pre className={command}>{job.command}</pre>
            )}
            <p className="text-[13px] text-muted-foreground">
              #{job.id} · <span className={cn('font-semibold', tone(job.status))}>{outcome(i18n, job)}</span>{' '}
              {when(i18n, job, now)}
            </p>
            {job.reason && <Reason job={job} reason={job.reason} />}
            {job.read_by.length > 0 && (
              <p className="flex flex-wrap gap-x-2 text-[13px] text-muted-foreground">
                {t('job.readBy')}
                {job.read_by.map((id) => (
                  <a key={id} href={href('sessione', { id: String(id) })} className={link}>
                    #{id}
                  </a>
                ))}
              </p>
            )}
            {job.purpose && (
              <details className="group">
                <summary className="cursor-pointer text-[12px] text-muted-foreground select-none hover:text-foreground">
                  {t('job.command')}
                </summary>
                <pre className={cn(command, 'mt-1.5')}>{job.command}</pre>
              </details>
            )}
          </li>
        ))}
      </ul>
    </section>
  )
}

/** A kill's cause is ours and is translated; a failure's line is the job's own output. */
function Reason({ job, reason }: { job: SessionJob; reason: string }) {
  const { t } = useI18n()
  if (job.status === 'killed' && reason.startsWith('time limit')) return <p className="text-[13px] text-bad">{t('job.reason.time')}</p>
  if (job.status === 'killed' && reason.startsWith('disk quota')) return <p className="text-[13px] text-bad">{t('job.reason.disk')}</p>
  return <p className="font-mono text-[12px] break-words text-bad">{reason}</p>
}

function tone(status: string) {
  return status === 'done' ? 'text-good' : status === 'running' ? 'text-live' : 'text-bad'
}

function outcome({ t }: I18n, job: SessionJob) {
  if (job.status === 'running') return t('job.running')
  if (job.status === 'done') return t('job.done')
  if (job.status === 'killed') return t('job.killed')
  if (job.status === 'failed') return job.exit_code === null ? t('job.failed') : t('job.failedCode', { code: job.exit_code })
  return job.status
}

function when(i18n: I18n, job: SessionJob, now: number) {
  const started = Date.parse(job.created_at)
  if (job.finished_at === null) {
    return i18n.t('job.runningFor', { duration: duration(i18n, now - started), max: i18n.tn('count.hours', job.max_hours) })
  }
  return i18n.t('job.after', { duration: duration(i18n, Date.parse(job.finished_at) - started) })
}

/** Jobs other sessions started whose files this one read, each back to its own session. */
export function ReadJobs({ jobs }: { jobs: ReadJob[] }) {
  const { t, lang } = useI18n()
  if (jobs.length === 0) return null
  return (
    <section aria-labelledby="session-jobs-read" className={cn(card, 'grid gap-3 text-[14px]')}>
      <h2 id="session-jobs-read" className="panel-label">{t('job.readTitle')}</h2>
      <ul className="grid divide-y">
        {jobs.map((job) => (
          <li key={job.id} className="grid min-w-0 gap-1.5 py-3 first:pt-0 last:pb-0">
            {job.purpose ? (
              <p className="font-medium text-pretty">
                <span lang="en">{job.purpose}</span>
                {lang !== 'en' && <LangBadge lang="en" className="ml-1.5" />}
              </p>
            ) : (
              <pre className={command}>{job.command}</pre>
            )}
            <p className="text-[13px] text-muted-foreground">
              #{job.id} ·{' '}
              <a href={href('sessione', { id: String(job.experiment_id) })} className={link}>
                {t('job.startedBy', { id: job.experiment_id })}
              </a>
            </p>
          </li>
        ))}
      </ul>
    </section>
  )
}
