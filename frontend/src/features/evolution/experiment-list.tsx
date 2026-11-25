import { ErrorNote, LoadingNote, StateNote, card } from '@/components/page'
import { useExperiments } from '@/lib/api'
import { ExperimentRow } from './experiment-row'

export function ExperimentList() {
  const experiments = useExperiments()
  const items = experiments.data?.pages.flatMap((p) => p.items) ?? []
  return (
    <section aria-labelledby="experiments" className="grid min-w-0 gap-4">
      <h2 id="experiments" className="text-[19px] font-semibold tracking-tight">Tutti gli esperimenti</h2>
      {experiments.isPending ? (
        <LoadingNote what="gli esperimenti" />
      ) : experiments.isError && items.length === 0 ? (
        <ErrorNote what="gli esperimenti" onRetry={() => void experiments.refetch()} />
      ) : items.length === 0 ? (
        <StateNote
          title="Nessun esperimento ancora"
          text="Appena l’agente consegna il primo tentativo, lo trovi qui con il verdetto dell’arbitro."
          className={card}
        />
      ) : (
        <>
          <ol className="grid gap-2">
            {items.map((e) => (
              <ExperimentRow key={e.id} experiment={e} />
            ))}
          </ol>
          {experiments.isFetchNextPageError && (
            <p role="alert" className="text-center text-[13px] text-bad">Non riesco a caricare gli esperimenti più vecchi.</p>
          )}
          {experiments.hasNextPage && (
            <button
              type="button"
              onClick={() => void experiments.fetchNextPage()}
              disabled={experiments.isFetchingNextPage}
              className="mx-auto h-9 cursor-pointer rounded-full bg-muted px-5 text-[13px] font-medium transition-colors hover:bg-border disabled:cursor-wait disabled:opacity-60"
            >
              {experiments.isFetchingNextPage ? 'Carico…' : 'Mostra altri'}
            </button>
          )}
        </>
      )}
    </section>
  )
}
