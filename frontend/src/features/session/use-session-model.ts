import { useMemo } from 'react'
import { useI18n } from '@/i18n/context'
import type { AgentEvent } from '@/lib/api'
import { buildSession, type SessionModel } from './model'

/** The session's log in the visitor's language, rebuilt when the events or the language change. */
export function useSessionModel(events: AgentEvent[]): SessionModel {
  const i18n = useI18n()
  return useMemo(() => buildSession(i18n, events), [i18n, events])
}

/** "Compila", for the start of a line. */
export const upper = (text: string) => (text ? text[0]?.toUpperCase() + text.slice(1) : text)
