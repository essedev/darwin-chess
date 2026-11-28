import { useI18n } from '@/i18n/context'
import { LangBadge } from '@/i18n/parts'
import type { Job } from '@/lib/api'
import { useNow } from '@/lib/use-now'
import { href } from '@/lib/use-route'
import { duration } from './format'

/**
 * The long jobs the agent left running, under what it is doing: what each is for, in the
 * agent's words, and for how long. How a job ended is on the page of its session.
 */
export function JobLine({ jobs }: { jobs: Job[] }) {
  const i18n = useI18n()
  const { t, tn, lang } = i18n
  const now = useNow(30000, jobs.length > 0)
  if (jobs.length === 0) return null
  return (
    <ul className="mx-auto grid w-full max-w-[620px] gap-3 border-t border-dashed pt-3 text-center">
      {jobs.map((job) => (
        <li key={job.id} className="grid min-w-0 gap-1">
          <p className="font-mono text-[11px] font-medium tracking-wider text-muted-foreground uppercase">
            <span aria-hidden className="mr-1.5 inline-block size-1.5 animate-pulse rounded-full bg-live align-[2px]" />
            {t('job.background')} ·{' '}
            {t('job.elapsed', {
              duration: duration(i18n, now - Date.parse(job.created_at)),
              max: tn('count.hours', job.max_hours),
            })}
          </p>
          <a
            href={href('sessione', { id: String(job.experiment_id) })}
            title={t('job.openSession')}
            className="min-w-0 cursor-pointer text-[14px] leading-snug font-medium text-pretty underline-offset-4 hover:underline"
          >
            {job.purpose ? (
              <>
                <span lang="en">{job.purpose}</span>
                {lang !== 'en' && <LangBadge lang="en" className="ml-1.5" />}
              </>
            ) : (
              <code className="block truncate font-mono text-xs">{job.command}</code>
            )}
          </a>
        </li>
      ))}
    </ul>
  )
}
