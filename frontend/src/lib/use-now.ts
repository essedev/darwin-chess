import { useEffect, useState } from 'react'

/** The current time, refreshed every `everyMs` while `active` (clocks, running times). */
export function useNow(everyMs: number, active = true): number {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    if (!active) return
    const timer = window.setInterval(() => setNow(Date.now()), everyMs)
    return () => window.clearInterval(timer)
  }, [everyMs, active])
  return now
}
