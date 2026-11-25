import { ChevronRight } from 'lucide-react'
import type { ReactNode } from 'react'
import { AgentMarkdown } from '@/components/markdown'
import { ErrorNote, LoadingNote, PageShell, StateNote, card } from '@/components/page'
import { dateTime } from '@/features/live/format'
import { useMind } from '@/lib/api'
import { cn } from '@/lib/utils'

export default function MindPage() {
  const mind = useMind()
  return (
    <PageShell
      title="Mente"
      intro="L’agente non ricorda nulla da una sessione all’altra: quello che sa lo scrive in due file, la strategia e gli appunti, e li rilegge ogni volta. Li scrive in inglese, la lingua in cui lavora. Sotto, le istruzioni che riceve da noi."
    >
      {mind.isPending ? (
        <LoadingNote what="la mente dell’agente" />
      ) : mind.isError ? (
        <ErrorNote what="la mente dell’agente" onRetry={() => void mind.refetch()} />
      ) : (
        <>
          {mind.data.updated_at && (
            <p className="-mt-3 text-[13px] text-muted-foreground">
              Ultimo aggiornamento: <time dateTime={mind.data.updated_at}>{dateTime(mind.data.updated_at)}</time>
            </p>
          )}
          <div className="grid items-start gap-4 lg:grid-cols-2">
            <Panel title="La strategia" hint="Il piano a lungo termine: dove vuole portare il motore e in che ordine.">
              {mind.data.strategy?.trim() ? (
                <AgentMarkdown text={mind.data.strategy} />
              ) : (
                <StateNote title="Nessuna strategia scritta ancora" text="L’agente la scrive dopo i primi tentativi." />
              )}
            </Panel>
            <Panel title="Gli appunti" hint="Cosa ha funzionato, cosa no, cosa provare: il suo quaderno di laboratorio.">
              {mind.data.notes?.trim() ? (
                <AgentMarkdown text={mind.data.notes} />
              ) : (
                <StateNote title="Nessun appunto ancora" text="Gli appunti si riempiono man mano che l’agente sperimenta." />
              )}
            </Panel>
          </div>
          <SystemPrompt text={mind.data.system_prompt} />
        </>
      )}
    </PageShell>
  )
}

function Panel({ title, hint, children }: { title: string; hint: string; children: ReactNode }) {
  return (
    <section className={cn(card, 'grid min-w-0 gap-3')}>
      <header className="grid gap-0.5 border-b pb-3">
        <h2 className="text-[17px] font-semibold tracking-tight">{title}</h2>
        <p className="text-[13px] text-muted-foreground">{hint}</p>
      </header>
      {children}
    </section>
  )
}

function SystemPrompt({ text }: { text: string | null }) {
  return (
    <details className={cn(card, 'group min-w-0 p-0')}>
      <summary className="flex cursor-pointer list-none items-start gap-2.5 rounded-[18px] p-5 hover:bg-muted/50 [&::-webkit-details-marker]:hidden">
        <ChevronRight aria-hidden className="mt-1 size-4 shrink-0 text-muted-foreground transition-transform group-open:rotate-90" />
        <span className="grid gap-0.5">
          <span className="text-[17px] font-semibold tracking-tight">Cosa gli diciamo noi</span>
          <span className="text-[13px] text-muted-foreground">
            Le istruzioni fisse che l’agente riceve all’inizio di ogni sessione, in inglese. Le scriviamo noi, lui non può cambiarle.
          </span>
        </span>
      </summary>
      <div className="border-t px-5 py-4">
        {text?.trim() ? (
          <pre className="overflow-x-auto font-mono text-[12.5px] leading-relaxed whitespace-pre-wrap">{text}</pre>
        ) : (
          <StateNote title="Istruzioni non disponibili" />
        )}
      </div>
    </details>
  )
}
