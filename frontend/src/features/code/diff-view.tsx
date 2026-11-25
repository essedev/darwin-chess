import { ErrorNote, LoadingNote, StateNote, card } from '@/components/page'
import { num } from '@/features/live/format'
import { isClientError, type DiffFile, useCodeDiff } from '@/lib/api'
import { href } from '@/lib/use-route'
import { cn } from '@/lib/utils'

const STATUS: Record<string, string> = {
  added: 'nuovo', A: 'nuovo',
  modified: 'modificato', M: 'modificato',
  deleted: 'eliminato', D: 'eliminato',
  renamed: 'rinominato', R: 'rinominato',
}

/** "gen-3" or "exp-12" from the link; anything else is not a diff we can ask for. */
function parse(diff: string): { query: string; title: string; ref: string } | null {
  const match = /^(gen|exp)-(\d+)$/.exec(diff)
  if (!match) return null
  const [, kind, id] = match
  return kind === 'gen'
    ? { query: `gen=${id}`, title: `Cosa è cambiato in gen-${id}`, ref: diff }
    : { query: `exp=${id}`, title: `Le modifiche del tentativo #${id}`, ref: diff }
}

export function DiffView({ diff }: { diff: string }) {
  const spec = parse(diff)
  const result = useCodeDiff(spec?.query ?? null)
  if (!spec) return <StateNote title="Questo link non è valido" text="Le modifiche si aprono da una generazione o da un esperimento." className={card} />
  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
        <h2 className="text-[19px] font-semibold tracking-tight">{spec.title}</h2>
        {result.data && (
          <span className="font-mono text-[12px] text-muted-foreground">
            {result.data.from.slice(0, 7)} → {result.data.to.slice(0, 7)}
          </span>
        )}
        <a href={href('codice', { ref: spec.ref })} className="cursor-pointer text-[13px] font-medium text-live underline-offset-4 hover:underline">
          Sfoglia tutto il codice di questa versione
        </a>
      </div>
      {result.isPending ? (
        <LoadingNote what="le modifiche" />
      ) : result.isError ? (
        isClientError(result.error) ? (
          <StateNote title="Modifiche non disponibili" text="Non trovo il codice di questa versione da confrontare." className={card} />
        ) : (
          <ErrorNote what="le modifiche" onRetry={() => void result.refetch()} />
        )
      ) : result.data.files.length === 0 ? (
        <StateNote title="Nessuna modifica al codice" className={card} />
      ) : (
        <DiffFiles files={result.data.files} />
      )}
    </div>
  )
}

function DiffFiles({ files }: { files: DiffFile[] }) {
  const additions = files.reduce((sum, f) => sum + f.additions, 0)
  const deletions = files.reduce((sum, f) => sum + f.deletions, 0)
  const openByDefault = files.length <= 8
  return (
    <>
      <p className="text-[13px] text-muted-foreground">
        {files.length === 1 ? '1 file' : `${files.length} file`} ·{' '}
        <span className="font-mono text-good">+{num(additions)}</span> <span className="font-mono text-bad">−{num(deletions)}</span> righe
      </p>
      <div className="grid gap-3">
        {files.map((file) => (
          <details key={file.path} open={openByDefault} className={cn(card, 'group min-w-0 overflow-hidden p-0')}>
            <summary className="flex cursor-pointer flex-wrap items-baseline gap-x-3 gap-y-1 px-4 py-3 hover:bg-muted/60">
              <span className="rounded-full bg-muted px-2 py-px text-[11px] font-medium text-muted-foreground">
                {STATUS[file.status] ?? file.status}
              </span>
              <span className="min-w-0 flex-1 font-mono text-[13px] font-medium break-all">{file.path}</span>
              <span className="font-mono text-[12px]">
                <span className="text-good">+{num(file.additions)}</span> <span className="text-bad">−{num(file.deletions)}</span>
              </span>
            </summary>
            <Patch patch={file.patch} />
          </details>
        ))}
      </div>
    </>
  )
}

const LINE_TONE: Record<string, string> = {
  '+': 'bg-good/12',
  '-': 'bg-bad/12',
  '@': 'bg-live/8 text-muted-foreground',
  '\\': 'text-muted-foreground',
}

/** A unified patch, each line coloured by its first character; git's file headers are dropped. */
function Patch({ patch }: { patch: string | null }) {
  if (!patch) return <p className="border-t px-4 py-3 text-[13px] text-muted-foreground">Nessuna differenza testuale da mostrare.</p>
  const lines = patch.replace(/\n$/, '').split('\n')
  const start = lines.findIndex((line) => line.startsWith('@@'))
  return (
    <div className="overflow-x-auto border-t py-1 font-mono text-[12.5px] leading-[1.65]">
      <div className="min-w-fit">
        {lines.slice(Math.max(0, start)).map((line, i) => (
          <div key={i} className={cn('pr-4 pl-3 whitespace-pre', LINE_TONE[line[0] ?? ''])}>
            {line || ' '}
          </div>
        ))}
      </div>
    </div>
  )
}
