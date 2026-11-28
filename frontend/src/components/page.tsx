import type { ReactNode } from 'react'
import { type Art, AsciiArt } from '@/components/ascii'
import { useT } from '@/i18n/context'
import { cn } from '@/lib/utils'

// The same surface as a Panel without a subject: a hairline and a 12px radius.
export const card = 'panel rounded-[12px] p-5'

/** A content page under the navigation: title, one plain line on what it shows, then the body. */
export function PageShell(props: { title: string; intro: ReactNode; children: ReactNode; className?: string; back?: ReactNode }) {
  return (
    <main className={cn('grid content-start gap-6 px-4 pb-10', props.back ? 'pt-3 sm:px-8 sm:pt-5' : 'pt-5 sm:px-8 sm:pt-7', props.className)}>
      {props.back && <div className="-mb-4">{props.back}</div>}
      <header className="grid gap-1.5">
        <h1 className="text-[26px] font-semibold tracking-tight sm:text-[30px]">{props.title}</h1>
        <p className="text-[15px] leading-relaxed text-pretty text-muted-foreground">{props.intro}</p>
      </header>
      {props.children}
    </main>
  )
}

/**
 * Loading, empty and error states, inside or outside a panel: a small ASCII animation over
 * the words (components/ascii.tsx). `art: false` keeps only the words, for tight spots.
 */
export function StateNote(props: {
  title: string
  text?: ReactNode
  tone?: 'muted' | 'bad'
  art?: Art | false
  big?: boolean
  className?: string
}) {
  const art = props.art ?? false
  return (
    <div
      className={cn('grid justify-items-center gap-2 py-6 text-center', props.big && 'py-16', props.className)}
      role={props.tone === 'bad' ? 'alert' : 'status'}
    >
      {art && <AsciiArt art={props.big || art !== 'loading' ? art : 'inline'} className="mb-1" />}
      <p className={cn('font-mono text-[13px] font-medium tracking-[0.02em]', props.tone === 'bad' && 'text-live')}>{props.title}</p>
      {props.text && <div className="max-w-[44ch] text-[13px] leading-normal text-muted-foreground">{props.text}</div>}
    </div>
  )
}

/** `what` is already translated, with its article: "gli esperimenti", "the experiments". */
export function LoadingNote({ what, big, className }: { what: string; big?: boolean; className?: string }) {
  const t = useT()
  return <StateNote art="loading" big={big} title={t('state.loading', { what })} className={className} />
}

export function ErrorNote(props: { what: string; onRetry?: () => void; big?: boolean; className?: string }) {
  const t = useT()
  return (
    <StateNote
      tone="bad"
      art="error"
      big={props.big}
      className={props.className}
      title={t('state.error', { what: props.what })}
      text={
        <>
          <p>{t('state.down')}</p>
          {props.onRetry && (
            <button
              type="button"
              onClick={props.onRetry}
              className="mt-3 h-8 cursor-pointer rounded-full bg-live px-4 font-mono text-[12px] font-medium text-white transition-opacity hover:opacity-90 focus-visible:ring-2 focus-visible:ring-ring/60 focus-visible:outline-none"
            >
              {t('state.retry')}
            </button>
          )}
        </>
      }
    />
  )
}
