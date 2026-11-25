import { ExternalLink } from 'lucide-react'
import { AgentMarkdown } from '@/components/markdown'
import { ErrorNote, LoadingNote, PageShell, card } from '@/components/page'
import { longDate } from '@/features/live/format'
import { useLab } from '@/lib/api'
import { cn } from '@/lib/utils'
import { CostPerGeneration, LabNumbers } from './lab-numbers'

const LINKS = [
  { href: 'https://lichess.org/@/darwin-chess-bot', label: 'Il bot su Lichess' },
  { href: 'https://esse.dev', label: 'Chi ha costruito il laboratorio' },
]

export default function LabPage() {
  const lab = useLab()
  return (
    <PageShell title="Laboratorio" intro="Come funziona l’esperimento, quanto costa e cosa è cambiato nel laboratorio stesso.">
      <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <HowItWorks />
        {lab.isPending ? (
          <LoadingNote what="i numeri" />
        ) : lab.isError ? (
          <ErrorNote what="i numeri" onRetry={() => void lab.refetch()} />
        ) : (
          <CostPerGeneration rows={lab.data.cost_per_generation} />
        )}
      </div>
      {lab.data && (
        <>
          <section aria-labelledby="numbers" className="grid gap-3">
            <h2 id="numbers" className="text-[19px] font-semibold tracking-tight">I numeri</h2>
            {lab.data.started_at && (
              <p className="-mt-1 text-[13px] text-muted-foreground">Il laboratorio è acceso dal {longDate(lab.data.started_at)}.</p>
            )}
            <LabNumbers totals={lab.data.totals} />
          </section>
          <section className={cn(card, 'grid min-w-0 gap-3')}>
            <h2 className="text-[17px] font-semibold tracking-tight">Le novità del laboratorio</h2>
            {lab.data.changelog.trim() ? (
              <AgentMarkdown text={withoutTitle(lab.data.changelog)} />
            ) : (
              <p className="py-4 text-center text-[14px] text-muted-foreground">Nessuna novità registrata.</p>
            )}
          </section>
        </>
      )}
      <ul className="flex flex-wrap gap-x-6 gap-y-2 text-[14px]">
        {LINKS.map((link) => (
          <li key={link.href}>
            <a href={link.href} target="_blank" rel="noopener" className="inline-flex cursor-pointer items-center gap-1.5 font-medium text-live underline-offset-4 hover:underline">
              {link.label}
              <ExternalLink aria-hidden className="size-3.5" />
            </a>
          </li>
        ))}
      </ul>
    </PageShell>
  )
}

function HowItWorks() {
  return (
    <section className={cn(card, 'grid min-w-0 gap-3 text-[15px] leading-relaxed text-pretty')}>
      <h2 className="text-[17px] font-semibold tracking-tight">Come funziona</h2>
      <p>
        Un’intelligenza artificiale scrive da zero un motore di scacchi in Rust e prova a renderlo più forte, una modifica
        alla volta. Ogni tentativo parte da un’idea, la sua ipotesi, e finisce con una nuova versione del codice.
      </p>
      <p>
        A decidere non è lei. Un arbitro che l’agente non può toccare compila il motore, controlla che rispetti le regole e
        lo fa giocare contro il campione in carica, partita dopo partita, finché il risultato non è chiaro. Se vince diventa
        la nuova generazione; se no il tentativo viene scartato, e l’agente si annota il perché.
      </p>
      <p>Il campione gioca anche su Lichess contro altri bot, così la sua forza si misura pure fuori dal laboratorio.</p>
      <p className="text-muted-foreground">
        Tutto questo ha un tetto: 2 dollari al giorno di chiamate al modello, distribuiti sulle ore. Quando il tetto è
        raggiunto, l’agente aspetta.
      </p>
    </section>
  )
}

/** The changelog opens with its own "# Changelog" title: the card already has one. */
function withoutTitle(markdown: string): string {
  return markdown.replace(/^\s*#\s[^\n]*\n/, '')
}
