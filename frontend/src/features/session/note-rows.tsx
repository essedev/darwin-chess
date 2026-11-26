import { useState } from 'react'
import { ClampText } from '@/components/clamp-text'
import { AgentMarkdown } from '@/components/markdown'
import { Help } from '@/components/panel'
import { plainText } from '@/features/live/format'
import { type I18n, useI18n } from '@/i18n/context'
import { cn } from '@/lib/utils'
import type { Note, Status } from './model'

const kicker = 'font-mono text-[10.5px] font-medium tracking-[0.12em] uppercase'

/**
 * A thought (what the agent writes between calls) or its reasoning, inline in the log. A
 * thought reads in Italian once translated, the original a click away; the reasoning stays
 * in English, the language it was written in (translating it would cost on every reply).
 */
export function NoteRow({ note }: { note: Note }) {
  const { t, f, lang } = useI18n()
  const [original, setOriginal] = useState(false)
  const reasoning = note.type === 'reasoning'
  const italian = !reasoning && lang === 'it' && note.italian ? note.italian : null
  const showItalian = italian !== null && !original
  const inEnglish = lang === 'it' && !showItalian
  return (
    <li className="grid min-w-0 gap-1.5 px-2.5 pt-2.5 pb-3 sm:pl-[86px]">
      <p className={cn(kicker, 'flex items-center gap-1.5', reasoning ? 'text-muted-foreground' : 'text-c-gens')}>
        {reasoning ? t('session.reasons') : t('session.thinks')} · {f.timeSeconds(note.at)}
        {inEnglish && `, ${t('caption.inEnglish')}`}
        {reasoning && <Help text={t('session.reasoningHelp')} />}
      </p>
      {italian && (
        <button
          type="button"
          onClick={() => setOriginal((value) => !value)}
          className="cursor-pointer justify-self-start rounded-sm text-[12px] font-medium text-live underline-offset-4 hover:underline focus-visible:ring-2 focus-visible:ring-ring/60 focus-visible:outline-none"
        >
          {original ? t('mind.showItalian') : t('mind.showOriginal')}
        </button>
      )}
      {reasoning ? (
        <ClampText text={plainText(note.text)} lang="en" className="max-w-[72ch] text-[14px] leading-relaxed text-muted-foreground" />
      ) : (
        <AgentMarkdown text={showItalian ? italian : note.text} lang={showItalian ? 'it' : 'en'} className="max-w-[72ch] text-[14.5px]" />
      )}
      {note.cut && <p className="text-[12px] text-muted-foreground">{t('session.cutText')}</p>}
    </li>
  )
}

/** Why a session stopped, from the orchestrator's English reason, in the visitor's words. */
function stopReason({ t }: I18n, reason: string): string {
  const minutes = /exceeded (\d+(?:\.\d+)?) minutes/.exec(reason)
  if (minutes) return t('session.stop.minutes', { n: minutes[1] ?? '' })
  const calls = /more than (\d+) tool calls/.exec(reason)
  if (calls) return t('session.stop.calls', { n: calls[1] ?? '' })
  if (/session cost/.test(reason)) return t('session.stop.cost')
  return reason
}

/** A dashed line across the log: the session starts, stops, hands its candidate over. */
export function StatusRow({ status, sessionId, base }: { status: Status; sessionId: number; base: number | null }) {
  const i18n = useI18n()
  const { t, f } = i18n
  const reason = typeof status.payload.reason === 'string' ? status.payload.reason : ''
  const text =
    status.state === 'started'
      ? base === null ? t('session.status.started', { id: sessionId }) : t('session.status.startedFrom', { id: sessionId, gen: base })
      : status.state === 'judging' ? t('session.status.judging')
      : status.state === 'stopped' ? t('session.status.stopped', { reason: stopReason(i18n, reason) })
      : status.state === 'provider_error' ? t('session.status.provider_error')
      : status.state
  return (
    <li className="flex items-center gap-3 p-2.5 text-center font-mono text-[12px] text-muted-foreground before:flex-1 before:border-t before:border-dashed before:content-[''] after:flex-1 after:border-t after:border-dashed after:content-['']">
      <span className="max-w-[80%]">
        {f.timeSeconds(status.at)} · {text}
      </span>
    </li>
  )
}

/** The end of a live log: the time now and a blinking cursor. */
export function CursorRow({ now }: { now: number }) {
  const { f } = useI18n()
  return (
    <li aria-hidden className="grid grid-cols-[56px_minmax(0,1fr)] gap-3 px-2.5 py-2 font-mono text-[12px] text-muted-foreground tabular-nums sm:grid-cols-[64px_minmax(0,1fr)]">
      <span>{f.timeSeconds(now)}</span>
      <b className="font-semibold text-live motion-safe:animate-[cursor-blink_1.1s_steps(1)_infinite]">▍</b>
    </li>
  )
}
