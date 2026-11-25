import { type ReactNode, useId } from 'react'
import { useT } from '@/i18n/context'
import { cn } from '@/lib/utils'

/** A raised surface: rounded, a full hairline and a soft drop (both themes in index.css). */
export const panel = 'rounded-[20px] bg-card shadow-[var(--panel-shadow)]'

/**
 * A panel with a header: the title on the left, an action (a link) on the right, a rule
 * under them. `help` adds a "?" that explains the title.
 */
export function Panel(props: {
  title: ReactNode
  action?: ReactNode
  help?: string
  children: ReactNode
  className?: string
}) {
  const id = useId()
  return (
    <section aria-labelledby={id} className={cn(panel, 'min-w-0 p-5', props.className)}>
      <header className="mb-3.5 flex items-center justify-between gap-3 border-b pb-3">
        <h2 id={id} className="flex items-center gap-1.5 text-[13px] font-medium">
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
          'rounded-[10px] bg-foreground px-3 py-2.5 text-left text-[12px] leading-snug font-normal tracking-normal text-background normal-case opacity-0 transition-opacity',
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
    <div className="mt-4 flex items-center justify-between gap-3 border-t pt-3 text-[12px] text-muted-foreground">
      {children}
    </div>
  )
}
