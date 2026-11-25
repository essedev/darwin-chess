import { lazy, Suspense, useEffect } from 'react'
import { Nav } from '@/components/nav'
import { LoadingNote } from '@/components/page'
import { LiveView } from '@/features/live/live-view'
import { TABS, useRoute } from '@/lib/use-route'

// The other pages load on demand: the live view stays as light as it was.
const EvolutionPage = lazy(() => import('@/features/evolution/evolution-page'))
const CodePage = lazy(() => import('@/features/code/code-page'))
const MindPage = lazy(() => import('@/features/mind/mind-page'))
const LabPage = lazy(() => import('@/features/lab/lab-page'))

export default function App() {
  const { page, params } = useRoute()

  useEffect(() => {
    const label = TABS.find((t) => t.page === page)?.label
    document.title = page === 'diretta' || !label ? 'darwin-chess' : `${label} · darwin-chess`
    window.scrollTo(0, 0)
  }, [page])

  return (
    <div className="flex min-h-svh flex-col">
      <Nav current={page} />
      <Suspense fallback={<LoadingNote what="la pagina" />}>
        {page === 'diretta' && <LiveView />}
        {page === 'evoluzione' && <EvolutionPage />}
        {page === 'codice' && <CodePage params={params} />}
        {page === 'mente' && <MindPage />}
        {page === 'laboratorio' && <LabPage />}
      </Suspense>
    </div>
  )
}
