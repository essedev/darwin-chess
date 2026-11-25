import { History } from '@/features/live/history'
import { SideCards } from '@/features/live/side-cards'
import { Stage } from '@/features/live/stage'
import { TopBar } from '@/features/live/top-bar'
import { useLichess, useLiveStream, useOverview } from '@/lib/api'

export default function App() {
  const overview = useOverview()
  const data = overview.data
  const { events, game, connected } = useLiveStream(data?.ready ? data.events : [])
  const lichess = useLichess()

  if (overview.isPending) return <Notice title="Carico la diretta…" />
  if (overview.isError)
    return <Notice title="Non riesco a raggiungere l’API" text="Controlla che il servizio api sia acceso (make dev-be)." />
  if (!data?.ready)
    return <Notice title="L’esperimento non è ancora partito" text="Il registro è vuoto: avvia l’orchestratore con make run-core." />

  return (
    <main className="mx-auto grid min-h-svh grid-cols-1 gap-x-9 gap-y-7 px-4 pt-4 pb-8 sm:px-8 sm:pt-6 sm:pb-10 lg:grid-cols-[270px_minmax(0,1fr)_320px] lg:grid-rows-[auto_1fr]">
      <TopBar data={data} connected={connected} />
      <History data={data} lichess={lichess.data?.performance[data.champion.id]} />
      <Stage data={data} game={game} events={events} lichess={lichess} />
      <SideCards data={data} />
    </main>
  )
}

function Notice({ title, text }: { title: string; text?: string }) {
  return (
    <main className="flex min-h-svh flex-col items-center justify-center gap-2 p-4 text-center">
      <h1 className="text-2xl font-semibold">{title}</h1>
      {text && <p className="text-muted-foreground">{text}</p>}
    </main>
  )
}
