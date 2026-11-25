import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

export const card = 'rounded-[18px] bg-card p-5 shadow-[inset_0_0_0_1px_var(--border)]'

/** A content page under the navigation: title, one plain line on what it shows, then the body. */
export function PageShell(props: { title: string; intro: ReactNode; children: ReactNode; className?: string }) {
  return (
    <main className={cn('grid content-start gap-6 px-4 pt-5 pb-10 sm:px-8 sm:pt-7', props.className)}>
      <header className="grid gap-1.5">
        <h1 className="text-[26px] font-semibold tracking-tight sm:text-[30px]">{props.title}</h1>
        <p className="text-[15px] leading-relaxed text-pretty text-muted-foreground">{props.intro}</p>
      </header>
      {props.children}
    </main>
  )
}

/** Loading, empty and error states share one quiet look, inside or outside a card. */
export function StateNote(props: { title: string; text?: ReactNode; tone?: 'muted' | 'bad'; className?: string }) {
  return (
    <div className={cn('grid gap-1 py-6 text-center', props.className)} role={props.tone === 'bad' ? 'alert' : undefined}>
      <p className={cn('text-[15px] font-medium', props.tone === 'bad' && 'text-bad')}>{props.title}</p>
      {props.text && <p className="text-[13px] text-muted-foreground">{props.text}</p>}
    </div>
  )
}

export function LoadingNote({ what }: { what: string }) {
  return <StateNote title={`Carico ${what}…`} />
}

export function ErrorNote({ what, onRetry }: { what: string; onRetry?: () => void }) {
  return (
    <StateNote
      tone="bad"
      title={`Non riesco a caricare ${what}`}
      text={
        onRetry ? (
          <button type="button" onClick={onRetry} className="cursor-pointer underline underline-offset-4 hover:text-foreground">
            Riprova
          </button>
        ) : (
          'Il servizio potrebbe essere momentaneamente spento: riprova tra poco.'
        )
      }
    />
  )
}
