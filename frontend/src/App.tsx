import { lazy, Suspense, useEffect } from 'react'
import { Nav } from '@/components/nav'
import { LoadingNote } from '@/components/page'
import { LiveView } from '@/features/live/live-view'
import { useI18n } from '@/i18n/context'
import { useRoute } from '@/lib/use-route'

// The other pages load on demand: the live view stays as light as it was.
const EvolutionPage = lazy(() => import('@/features/evolution/evolution-page'))
const CodePage = lazy(() => import('@/features/code/code-page'))
const MindPage = lazy(() => import('@/features/mind/mind-page'))
const LabPage = lazy(() => import('@/features/lab/lab-page'))
const SessionPage = lazy(() => import('@/features/session/session-page'))
const GamesPage = lazy(() => import('@/features/lichess/games-page'))
const GamePage = lazy(() => import('@/features/lichess/game-page'))

export default function App() {
  const { page, params } = useRoute()
  const { t } = useI18n()
  const label = t(`nav.${page}`)

  useEffect(() => {
    document.title = page === 'diretta' ? 'darwin-chess' : `${label} · darwin-chess`
  }, [page, label])

  useEffect(() => {
    window.scrollTo(0, 0)
  }, [page])

  return (
    <div className="flex min-h-svh flex-col">
      <Nav current={page} />
      <Suspense
        fallback={
          // A page's code is loading: the big knight in the middle of the page, as the live view does.
          <main className="flex flex-1 items-center justify-center p-4">
            <LoadingNote big what={t('what.page')} />
          </main>
        }
      >
        {page === 'diretta' && <LiveView />}
        {page === 'evoluzione' && <EvolutionPage />}
        {page === 'codice' && <CodePage params={params} />}
        {page === 'mente' && <MindPage />}
        {page === 'laboratorio' && <LabPage />}
        {page === 'sessione' && <SessionPage params={params} />}
        {page === 'partite' && <GamesPage params={params} />}
        {page === 'partita' && <GamePage params={params} />}
      </Suspense>
    </div>
  )
}
