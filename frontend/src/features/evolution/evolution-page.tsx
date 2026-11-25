import { PageShell } from '@/components/page'
import { ExperimentList } from './experiment-list'
import { GenerationTimeline } from './generation-timeline'

export default function EvolutionPage() {
  return (
    <PageShell
      title="Evoluzione"
      intro="Ogni generazione è una versione del motore che ha battuto la precedente in partite vere. In mezzo, tutti i tentativi dell’agente: quelli promossi e quelli scartati."
    >
      <div className="grid items-start gap-10 xl:grid-cols-2 xl:gap-12">
        <GenerationTimeline />
        <ExperimentList />
      </div>
    </PageShell>
  )
}
