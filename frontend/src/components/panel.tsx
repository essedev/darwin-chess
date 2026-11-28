import { Popover } from '@base-ui/react/popover'
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

/**
 * A "?" that shows a short explanation on hover, on focus and on tap. The explanation sits in a
 * portal and is shifted to stay on screen, so a "?" near an edge neither clips it nor widens
 * the page.
 */
export function Help({ text }: { text: string }) {
  const t = useT()
  return (
    <Popover.Root>
      <Popover.Trigger
        openOnHover
        delay={0}
        closeDelay={0}
        aria-label={t('help.label')}
        className="inline-flex size-4 cursor-help items-center justify-center rounded-full bg-muted font-sans text-[10px] font-semibold text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring/60 focus-visible:outline-none"
      >
        ?
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Positioner side="top" sideOffset={8} collisionPadding={16} className="z-30">
          <Popover.Popup
            className={cn(
              'w-64 max-w-[calc(100vw-32px)] rounded-[10px] bg-foreground px-3 py-2.5 text-left font-sans text-[12px] leading-snug font-normal tracking-normal text-background normal-case outline-none',
              'transition-opacity duration-100 data-[ending-style]:opacity-0 data-[starting-style]:opacity-0',
            )}
          >
            {text}
          </Popover.Popup>
        </Popover.Positioner>
      </Popover.Portal>
    </Popover.Root>
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
