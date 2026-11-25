import { useState } from 'react'
import { ErrorNote, LoadingNote, StateNote } from '@/components/page'
import { panel } from '@/components/panel'
import { useI18n } from '@/i18n/context'
import { useExperimentPage } from '@/lib/api'
import { cn } from '@/lib/utils'
import { ExperimentRow } from './experiment-row'

const PER_PAGE = 10

/** The filters, each a set of statuses; the empty set is every experiment. */
const FILTERS = {
  all: [],
  accepted: ['accepted'],
  rejected: ['rejected', 'stale', 'abandoned'],
  error: ['error', 'budget_stop'],
} as const satisfies Record<string, readonly string[]>
type Filter = keyof typeof FILTERS
const ORDER: Filter[] = ['all', 'accepted', 'rejected', 'error']

/** Every experiment, newest first, ten at a time, filtered by outcome. */
export function ExperimentList() {
  const { t, f } = useI18n()
  const [filter, setFilter] = useState<Filter>('all')
  // The cursors of the pages seen so far: going back pops one, going on pushes the next.
  const [cursors, setCursors] = useState<(number | null)[]>([null])
  const cursor = cursors.at(-1) ?? null
  const page = useExperimentPage(FILTERS[filter], cursor, PER_PAGE)
  const items = page.data?.items ?? []
  const counts = page.data?.counts
  const count = (key: Filter) =>
    counts ? (key === 'all' ? counts.total : FILTERS[key].reduce((sum, status) => sum + (counts[status] ?? 0), 0)) : null
  const shown = count(filter)
  const first = (cursors.length - 1) * PER_PAGE + 1
  const choose = (next: Filter) => {
    setFilter(next)
    setCursors([null])
  }
  return (
    <section aria-labelledby="experiments" className="grid min-w-0 content-start gap-4">
      <h2 id="experiments" className="flex items-baseline gap-2 text-[19px] font-semibold tracking-tight">
        {t('experiments.title')}
        {counts && <span className="text-[15px] font-normal text-muted-foreground tabular-nums">{f.num(counts.total)}</span>}
      </h2>
      <div role="group" aria-label={t('experiments.filter')} className="inline-flex w-fit max-w-full flex-wrap rounded-[14px] bg-muted p-[3px]">
        {ORDER.map((key) => (
          <button
            key={key}
            type="button"
            aria-pressed={filter === key}
            onClick={() => choose(key)}
            className={cn(
              'inline-flex h-7 cursor-pointer items-center gap-1.5 rounded-[11px] px-3 text-[13px] font-medium transition-colors',
              filter === key ? 'bg-card text-foreground shadow-[0_1px_2px_rgb(0_0_0/0.12)]' : 'text-muted-foreground hover:text-foreground',
            )}
          >
            {t(`experiments.filter.${key}`)}
            {count(key) !== null && <span className="font-mono text-[11px] text-muted-foreground tabular-nums">{count(key)}</span>}
          </button>
        ))}
      </div>
      {page.isPending ? (
        <LoadingNote what={t('what.experiments')} />
      ) : page.isError && items.length === 0 ? (
        <ErrorNote what={t('what.experiments')} onRetry={() => void page.refetch()} />
      ) : items.length === 0 ? (
        filter === 'all' ? (
          <StateNote art="empty" title={t('experiments.none.title')} text={t('experiments.none.text')} className={cn(panel, 'p-5')} />
        ) : (
          <StateNote title={t('experiments.noneHere')} className={cn(panel, 'p-5')} />
        )
      ) : (
        <>
          <ol className={cn('grid gap-0.5 transition-opacity', page.isPlaceholderData && 'opacity-60')}>
            {items.map((e) => (
              <ExperimentRow key={e.id} experiment={e} />
            ))}
          </ol>
          <div className="flex items-center justify-between gap-3 text-[13px] text-muted-foreground">
            <span className="tabular-nums">
              {shown !== null && t('experiments.range', { from: f.num(first), to: f.num(first + items.length - 1), of: f.num(shown) })}
            </span>
            <span className="flex gap-1.5">
              <PageButton disabled={cursors.length === 1} onClick={() => setCursors((all) => all.slice(0, -1))}>
                {t('experiments.newer')}
              </PageButton>
              <PageButton
                disabled={!page.data?.next_before_id || page.isPlaceholderData}
                onClick={() => {
                  const next = page.data?.next_before_id
                  if (next) setCursors((all) => [...all, next])
                }}
              >
                {t('experiments.older')}
              </PageButton>
            </span>
          </div>
        </>
      )}
    </section>
  )
}

function PageButton({ disabled, onClick, children }: { disabled: boolean; onClick: () => void; children: string }) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className="h-8 cursor-pointer rounded-full bg-card px-3.5 text-[13px] font-medium text-foreground shadow-[inset_0_0_0_1px_var(--border)] transition-colors hover:bg-muted disabled:cursor-default disabled:opacity-40 disabled:hover:bg-card"
    >
      {children}
    </button>
  )
}
