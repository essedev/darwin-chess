import { useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import type { AgentEvent } from '@/lib/api'

/**
 * The events of one running session as they happen, from the same SSE stream the live page
 * reads. Only while `active`: a finished session has nothing more to say. A status event
 * (the session ends, the candidate goes to the referee) refetches the session.
 */
export function useSessionStream(experimentId: number | null, active: boolean): AgentEvent[] {
  const queryClient = useQueryClient()
  // Keyed by session: moving to another session starts from nothing without an extra render.
  const [stream, setStream] = useState<{ id: number | null; events: AgentEvent[] }>({ id: null, events: [] })
  useEffect(() => {
    if (experimentId === null || !active) return
    const source = new EventSource('/api/stream')
    source.addEventListener('agent', (message) => {
      const event = JSON.parse((message as MessageEvent<string>).data) as AgentEvent
      if (event.experiment_id !== experimentId) return
      setStream((previous) => ({
        id: experimentId,
        events: [...(previous.id === experimentId ? previous.events.slice(-499) : []), event],
      }))
      if (event.kind === 'status') void queryClient.invalidateQueries({ queryKey: ['session', experimentId] })
    })
    return () => source.close()
  }, [experimentId, active, queryClient])
  return stream.id === experimentId ? stream.events : NONE
}

const NONE: AgentEvent[] = []
