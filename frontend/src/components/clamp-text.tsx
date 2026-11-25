import { useEffect, useId, useRef, useState } from 'react'
import { useT } from '@/i18n/context'
import { cn } from '@/lib/utils'

/**
 * A text cut at two lines, with "read all" under it when something is cut: the whole text
 * opens in place, so a commentary never needs another site to be read.
 */
export function ClampText({ text, lang, className }: { text: string; lang?: string; className?: string }) {
  const t = useT()
  const id = useId()
  const ref = useRef<HTMLParagraphElement>(null)
  const [open, setOpen] = useState(false)
  const [cut, setCut] = useState(false)
  useEffect(() => {
    const element = ref.current
    if (!element) return
    // Re-measured on every resize: the column width decides whether two lines are enough.
    const observer = new ResizeObserver(() => setCut(element.scrollHeight > element.clientHeight + 1))
    observer.observe(element)
    return () => observer.disconnect()
  }, [text])
  return (
    <div>
      <p ref={ref} id={id} lang={lang} className={cn(className, !open && 'line-clamp-2')}>
        {text}
      </p>
      {(cut || open) && (
        <button
          type="button"
          aria-expanded={open}
          aria-controls={id}
          onClick={() => setOpen((value) => !value)}
          className="mt-1 cursor-pointer rounded-sm text-[12px] font-medium text-foreground/80 underline-offset-4 hover:text-foreground hover:underline focus-visible:ring-2 focus-visible:ring-ring/60 focus-visible:outline-none"
        >
          {open ? t('text.less') : t('text.more')}
        </button>
      )}
    </div>
  )
}
