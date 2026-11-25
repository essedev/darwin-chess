import { ChevronRight } from 'lucide-react'
import { type ReactNode, useId, useState } from 'react'
import { cn } from '@/lib/utils'

/**
 * A one-line row that opens in place to show its details. `columns` sets the grid of the
 * line (the chevron takes the last 16px). Without `children` the row is plain text.
 */
export function ExpandRow({ columns, line, children }: { columns: string; line: ReactNode; children?: ReactNode }) {
  const [open, setOpen] = useState(false)
  const id = useId()
  const grid = cn('grid w-full items-center gap-3 px-3 py-2.5 text-left', columns)
  if (!children) return <li className={grid}>{line}</li>
  return (
    <li>
      <button
        type="button"
        aria-expanded={open}
        aria-controls={id}
        onClick={() => setOpen((value) => !value)}
        className={cn(
          grid,
          'cursor-pointer rounded-[12px] transition-colors hover:bg-muted/70 focus-visible:ring-2 focus-visible:ring-ring/60 focus-visible:outline-none',
          open && 'rounded-b-none bg-muted hover:bg-muted',
        )}
      >
        {line}
        <ChevronRight aria-hidden className={cn('size-4 text-muted-foreground transition-transform', open && 'rotate-90')} />
      </button>
      {open && (
        <div id={id} className="grid gap-2.5 rounded-b-[12px] bg-muted px-4 pt-1 pb-4 text-[13px] leading-normal">
          {children}
        </div>
      )}
    </li>
  )
}

/** A label and its value, inline, in the details of a row. */
export function Fact({ label, children }: { label: string; children: ReactNode }) {
  return (
    <span className="inline-flex flex-wrap items-center gap-1.5 text-muted-foreground">
      {label} <b className="font-medium text-foreground">{children}</b>
    </span>
  )
}
