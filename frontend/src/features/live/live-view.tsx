import { useI18n } from '@/i18n/context'
import { useLichess, useLiveStream, useOverview } from '@/lib/api'
import { History } from './history'
import { SideCards } from './side-cards'
import { Stage } from './stage'
import { TopBar } from './top-bar'

export function LiveView() {
  const { t } = useI18n()
  const overview = useOverview()
  const data = overview.data
  const { events, game, connected } = useLiveStream(data?.ready ? data.events : [])
  const lichess = useLichess()

  if (overview.isPending) return <Notice title={t('live.loading')} />
  if (overview.isError) return <Notice title={t('live.apiDown.title')} text={t('live.apiDown.text')} />
  if (!data?.ready) return <Notice title={t('live.notStarted.title')} text={t('live.notStarted.text')} />

  return (
    <main className="mx-auto grid flex-1 grid-cols-1 gap-x-9 gap-y-7 px-4 pt-4 pb-8 sm:px-8 sm:pt-6 sm:pb-10 lg:grid-cols-[270px_minmax(0,1fr)_320px] lg:grid-rows-[auto_1fr]">
      <TopBar data={data} connected={connected} />
      <History data={data} lichess={lichess.data?.performance[data.champion.id]} />
      <Stage data={data} game={game} events={events} lichess={lichess} />
      <SideCards data={data} />
    </main>
  )
}

function Notice({ title, text }: { title: string; text?: string }) {
  return (
    <main className="flex flex-1 flex-col items-center justify-center gap-2 p-4 text-center">
      <h1 className="text-2xl font-semibold">{title}</h1>
      {text && <p className="text-muted-foreground">{text}</p>}
    </main>
  )
}
