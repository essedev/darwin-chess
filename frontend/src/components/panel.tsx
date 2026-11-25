import { type ReactNode, useId } from 'react'
import { useT } from '@/i18n/context'
import { type Hue, hueStyle } from '@/lib/hue'
import { cn } from '@/lib/utils'

/** A surface: a hairline, a radius, nothing else. Tinted when it has a hue (see index.css). */
export const panel = 'panel rounded-[12px]'

/**
 * A panel with a header: a small coloured label on the left, an action (a link) on the right,
 * a dashed rule under them. `hue` colours it by subject; `help` adds a "?" to the label.
 */
export function Panel(props: {
  title: ReactNode
  action?: ReactNode
  help?: string
  hue?: Hue
  children: ReactNode
  className?: string
}) {
  const id = useId()
  return (
    <section aria-labelledby={id} style={hueStyle(props.hue)} className={cn(panel, 'min-w-0 p-5', props.className)}>
      <header className="panel-rule mb-3.5 flex items-center justify-between gap-3 pb-3">
        <h2 id={id} className="panel-label flex items-center gap-1.5">
          {props.title}
          {props.help && <Help text={props.help} />}
        </h2>
        {props.action}
      </header>
      {props.children}
    </section>
  )
}

/** A "?" that shows a short explanation on hover, on focus and on tap. */
export function Help({ text }: { text: string }) {
  const t = useT()
  const id = useId()
  return (
    <span className="group relative inline-flex">
      <button
        type="button"
        aria-label={t('help.label')}
        aria-describedby={id}
        className="inline-flex size-4 cursor-help items-center justify-center rounded-full bg-muted font-sans text-[10px] font-semibold text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring/60 focus-visible:outline-none"
      >
        ?
      </button>
      <span
        role="tooltip"
        id={id}
        className={cn(
          'pointer-events-none invisible absolute bottom-[calc(100%+8px)] left-1/2 z-30 w-64 max-w-[calc(100vw-32px)] -translate-x-1/2',
          'rounded-[10px] bg-foreground px-3 py-2.5 text-left font-sans text-[12px] leading-snug font-normal tracking-normal text-background normal-case opacity-0 transition-opacity',
          'group-focus-within:visible group-focus-within:opacity-100 group-hover:visible group-hover:opacity-100',
        )}
      >
        {text}
      </span>
    </span>
  )
}

/** A quiet link at the end of a panel, for "all of these" elsewhere. */
export function PanelFooter({ children }: { children: ReactNode }) {
  return (
    <div className="mt-4 flex items-center justify-between gap-3 border-t border-dashed pt-3 text-[12px] text-muted-foreground">
      {children}
    </div>
  )
}
