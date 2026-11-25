import { useState } from 'react'
import { useI18n } from '@/i18n/context'
import { useLichess, useLiveStream, useOverview } from '@/lib/api'
import { History } from './history'
import { SideCards } from './side-cards'
import { Stage, type Tab } from './stage'
import { TopBar } from './top-bar'

/**
 * Three columns that end at about the same height: how strong the champion is and the last
 * generations on the left, the game in the middle, the verdict, the spend and the last three
 * results on the right. Nothing here grows with the history: that lives in Evoluzione.
 */
export function LiveView() {
  const { t } = useI18n()
  const overview = useOverview()
  const data = overview.data
  const { events, game, connected } = useLiveStream(data?.ready ? data.events : [])
  const lichess = useLichess()
  const [tab, setTab] = useState<Tab>(() => (window.location.hash === '#lichess' ? 'lichess' : 'arena'))
  const choose = (next: Tab) => {
    setTab(next)
    // The Lichess tab has its own address, so a link can open the dashboard on it.
    window.history.replaceState(null, '', next === 'lichess' ? '#lichess' : window.location.pathname)
  }

  if (overview.isPending) return <Notice title={t('live.loading')} />
  if (overview.isError) return <Notice title={t('live.apiDown.title')} text={t('live.apiDown.text')} />
  if (!data?.ready) return <Notice title={t('live.notStarted.title')} text={t('live.notStarted.text')} />

  return (
    <main className="mx-auto grid w-full max-w-[1440px] flex-1 grid-cols-1 content-start gap-x-8 gap-y-7 px-4 pt-4 pb-10 sm:px-8 sm:pt-6 lg:grid-cols-[minmax(0,1fr)_300px] xl:grid-cols-[280px_minmax(0,1fr)_320px]">
      <TopBar data={data} connected={connected} />
      <History data={data} lichess={lichess.data?.performance[data.champion.id]} />
      <Stage data={data} game={game} events={events} lichess={lichess} tab={tab} onTab={choose} />
      <SideCards data={data} tab={tab} lichess={lichess} />
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
