import { ChevronRight } from 'lucide-react'
import { useId, useState } from 'react'
import { duration } from '@/features/live/format'
import { useI18n } from '@/i18n/context'
import { cn } from '@/lib/utils'
import { editsOf, lineDiff, TONE } from './describe'
import type { Call, Result } from './model'
import { upper } from './use-session-model'

const OUTPUT_LINES = 14
const OUTPUT_CHARS = 1400

const label = 'mt-1.5 font-mono text-[10.5px] font-medium tracking-[0.1em] text-muted-foreground uppercase'
const code =
  'max-w-full rounded-[8px] bg-card px-3 py-2.5 font-mono text-[12px] leading-[1.55] whitespace-pre-wrap [overflow-wrap:anywhere] shadow-[inset_0_0_0_1px_var(--border)]'
const note = 'text-[12px] text-muted-foreground'

/** One line of the log: time, the sentence, what came back; it opens on the raw call. */
export function CallRow({ call, live, now }: { call: Call; live: boolean; now: number }) {
  const i18n = useI18n()
  const { t, f } = i18n
  const [open, setOpen] = useState(false)
  const id = useId()
  const waiting = !call.result
  return (
    <li>
      <button
        type="button"
        aria-expanded={open}
        aria-controls={id}
        onClick={() => setOpen((value) => !value)}
        className={cn(
          'grid w-full cursor-pointer grid-cols-[56px_minmax(0,1fr)_16px] items-baseline gap-3 rounded-[10px] px-2.5 py-2 text-left text-[14px] transition-colors sm:grid-cols-[64px_minmax(0,1fr)_16px]',
          'hover:bg-muted/70 focus-visible:ring-2 focus-visible:ring-ring/60 focus-visible:outline-none',
          open && 'rounded-b-none bg-muted hover:bg-muted',
        )}
      >
        <span className="font-mono text-[12px] text-muted-foreground tabular-nums">{f.timeSeconds(call.at)}</span>
        <span className="min-w-0 [overflow-wrap:anywhere]">
          <span className={cn(waiting && live && 'text-live')}>{upper(call.desc.text)}</span>
          <span
            className={cn(
              'block text-[12.5px] md:ml-2.5 md:inline',
              call.out ? TONE[call.out.tone] : waiting && live ? 'text-live' : 'text-muted-foreground',
              call.out?.mono && 'font-mono text-[12px]',
            )}
          >
            {call.out ? call.out.text : live ? t('session.pending') : t('session.noAnswer')}
          </span>
        </span>
        <ChevronRight aria-hidden className={cn('size-4 self-center text-muted-foreground transition-transform', open && 'rotate-90')} />
      </button>
      {open && (
        <div id={id} className="mb-1.5 grid min-w-0 gap-2 rounded-b-[10px] bg-muted px-3 pt-1 pb-3.5">
          <RawCall call={call} />
          {call.result ? (
            <>
              <p className={label}>
                {t('session.raw.answer', { time: f.timeSeconds(call.result.at), after: span(Date.parse(call.result.at) - Date.parse(call.at)) })}
              </p>
              <Output result={call.result} />
            </>
          ) : (
            <>
              <p className={label}>{t('session.raw.answerLabel')}</p>
              <p className={note}>
                {live ? t('session.raw.waiting', { duration: duration(i18n, now - Date.parse(call.at)) }) : t('session.raw.none')}
              </p>
            </>
          )}
        </div>
      )}
    </li>
  )
}

/** "3 s", "2 min 5 s": how long an answer took. */
function span(ms: number): string {
  const s = Math.max(0, Math.round(ms / 1000))
  return s < 60 ? `${s} s` : `${Math.floor(s / 60)} min${s % 60 ? ` ${s % 60} s` : ''}`
}

/** The call as the agent made it: the command, the edit as a diff, the file written. */
function RawCall({ call }: { call: Call }) {
  const { t } = useI18n()
  const a = call.args
  const path = typeof a.path === 'string' ? a.path : ''
  const edits = call.tool === 'edit' ? editsOf(a) : []
  const heading = edits.length ? t('session.raw.edit', { path })
    : call.tool === 'bash' ? t('session.raw.command')
    : call.tool === 'write' ? t('session.raw.write')
    : t('session.raw.call')
  return (
    <>
      <p className={label}>{heading}</p>
      {edits.length ? <EditDiff edits={edits} /> : <pre className={code}>{callText(call)}</pre>}
      {call.cut && <p className={note}>{call.legacy ? t('session.cutArgsLegacy') : t('session.cutArgs')}</p>}
    </>
  )
}

function callText(call: Call): string {
  const a = call.args
  if (call.tool === 'bash' && typeof a.command === 'string') return `$ ${a.command}`
  if (call.tool === 'write' && typeof a.path === 'string') return `${a.path}\n\n${typeof a.content === 'string' ? a.content : ''}`
  const entries = Object.entries(a)
  if (!entries.length) return call.rawArgs ? `${call.tool} ${call.rawArgs}` : `${call.tool}()`
  return `${call.tool}(${entries.map(([k, v]) => `${k}: ${typeof v === 'string' ? `"${v}"` : JSON.stringify(v)}`).join(', ')})`
}

function EditDiff({ edits }: { edits: { oldText: string; newText: string }[] }) {
  return (
    <div className="overflow-hidden rounded-[8px] bg-card py-2 font-mono text-[12px] leading-[1.55] shadow-[inset_0_0_0_1px_var(--border)]">
      {edits.map((edit, i) => (
        <div key={i}>
          {i > 0 && <div className="pl-3 text-muted-foreground">  ⋯</div>}
          {lineDiff(edit.oldText, edit.newText).map(([kind, line], j) => (
            <div
              key={j}
              className={cn(
                'pr-3 pl-7 -indent-4 whitespace-pre-wrap [overflow-wrap:anywhere]',
                kind === '+' ? 'bg-good/12 text-[var(--code-string)]' : kind === '-' ? 'bg-bad/10 text-[var(--code-keyword)]' : 'text-muted-foreground',
              )}
            >
              {`${kind === '-' ? '−' : kind} ${line}`}
            </div>
          ))}
        </div>
      ))}
    </div>
  )
}

/** The answer as it came back; a long one is shortened, with the rest one click away. */
export function Output({ result }: { result: Result }) {
  const { t, f } = useI18n()
  const [full, setFull] = useState(false)
  const lines = result.text.split('\n')
  const long = lines.length > OUTPUT_LINES || result.text.length > OUTPUT_CHARS
  const shown = full || !long ? result.text : `${lines.slice(0, OUTPUT_LINES).join('\n').slice(0, OUTPUT_CHARS)}\n…`
  return (
    <>
      <pre className={cn(code, result.error && 'text-bad')}>{shown}</pre>
      {long && (
        <button
          type="button"
          aria-expanded={full}
          onClick={() => setFull((value) => !value)}
          className="cursor-pointer justify-self-start rounded-sm text-[12px] font-medium text-live underline-offset-4 hover:underline focus-visible:ring-2 focus-visible:ring-ring/60 focus-visible:outline-none"
        >
          {full ? t('text.less') : t('session.showAll', { n: f.num(result.text.length) })}
        </button>
      )}
      {(full || !long) && result.cut && <p className={note}>{t('session.cutAnswer')}</p>}
    </>
  )
}
