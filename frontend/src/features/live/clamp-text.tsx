import { useId, useLayoutEffect, useRef, useState } from 'react'
import type { Lang } from '@/i18n/context'
import { useT } from '@/i18n/context'
import { LangBadge } from '@/i18n/parts'
import { cn } from '@/lib/utils'

const CLAMP = { 2: 'line-clamp-2', 3: 'line-clamp-3' } as const

/**
 * A paragraph cut to a few lines that opens in place on click. The toggle shows only when
 * the text is actually cut, so a short commentary is not dressed up as a control.
 * `badge` marks a text shown in its original language because the translation is missing.
 */
export function ClampText(props: { text: string; lang: Lang; badge?: boolean; lines?: 2 | 3; className?: string }) {
  const t = useT()
  const id = useId()
  const box = useRef<HTMLParagraphElement>(null)
  const [open, setOpen] = useState(false)
  const [cut, setCut] = useState(false)

  useLayoutEffect(() => {
    const el = box.current
    // While open nothing is cut: keep the last measure so the toggle can close it again.
    if (!el || open) return
    const measure = () => setCut(el.scrollHeight > el.clientHeight + 1)
    measure()
    const observer = new ResizeObserver(measure)
    observer.observe(el)
    return () => observer.disconnect()
  }, [props.text, open])

  const toggle = cut || open ? () => setOpen((value) => !value) : undefined
  return (
    <div className={cn('grid justify-items-start gap-0.5', props.className)}>
      <p
        ref={box}
        id={id}
        lang={props.lang}
        onClick={toggle}
        className={cn('text-pretty', !open && CLAMP[props.lines ?? 3], toggle && 'cursor-pointer')}
      >
        {props.badge && <LangBadge lang={props.lang} className="mr-1.5" />}
        {props.text}
      </p>
      {toggle && (
        <button
          type="button"
          aria-expanded={open}
          aria-controls={id}
          onClick={toggle}
          className="cursor-pointer text-[12px] font-medium text-live underline-offset-4 hover:underline"
        >
          {open ? t('list.less') : t('list.more')}
        </button>
      )}
    </div>
  )
}
