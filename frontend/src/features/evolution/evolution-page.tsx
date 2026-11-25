import { PageShell } from '@/components/page'
import { useT } from '@/i18n/context'
import { ExperimentList } from './experiment-list'
import { GenerationTimeline } from './generation-timeline'

export default function EvolutionPage() {
  const t = useT()
  return (
    <PageShell title={t('nav.evoluzione')} intro={t('evolution.intro')}>
      <div className="grid items-start gap-10 xl:grid-cols-2 xl:gap-12">
        <GenerationTimeline />
        <ExperimentList />
      </div>
    </PageShell>
  )
}
