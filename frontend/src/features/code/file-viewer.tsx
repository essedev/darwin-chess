import { useMemo } from 'react'
import { ErrorNote, LoadingNote, StateNote } from '@/components/page'
import { num } from '@/features/live/format'
import { isClientError, type CodeFile, useCodeFile } from '@/lib/api'
import { highlightLines } from './highlight'

/** One file of a commit, with line numbers and syntax colours. */
export function FileViewer({ commit, path }: { commit: string; path: string | null }) {
  const file = useCodeFile(commit, path)
  if (path === null) return <StateNote title="Scegli un file" text="Il codice del motore è nell’elenco dei file." />
  if (file.isPending) return <LoadingNote what="il file" />
  if (file.isError) {
    return isClientError(file.error) ? (
      <StateNote title="Questo file non c’è in questa versione" text="Forse è stato aggiunto dopo, o rinominato: scegline un altro." />
    ) : (
      <ErrorNote what="il file" onRetry={() => void file.refetch()} />
    )
  }
  return <FileBody file={file.data} />
}

function FileBody({ file }: { file: CodeFile }) {
  const lines = useMemo(
    () => (file.content ? highlightLines(file.content, file.path) : []),
    [file.content, file.path],
  )
  return (
    <div className="grid min-w-0">
      <p className="flex flex-wrap items-baseline gap-x-3 border-b px-4 py-3 text-[12px] text-muted-foreground">
        <span className="font-mono text-[13px] font-medium break-all text-foreground">{file.path}</span>
        <span>{size(file.size)}</span>
        {lines.length > 0 && <span>{lines.length === 1 ? '1 riga' : `${num(lines.length)} righe`}</span>}
      </p>
      {file.truncated && (
        <p className="border-b bg-live/8 px-4 py-2 text-[12px] text-muted-foreground">
          Il file è molto lungo: qui ne vedi solo l’inizio.
        </p>
      )}
      {file.binary ? (
        <StateNote title="File binario, non mostrato" />
      ) : lines.length === 0 ? (
        <StateNote title="File vuoto" />
      ) : (
        <div className="overflow-x-auto py-2 font-mono text-[12.5px] leading-[1.65]">
          <div className="min-w-fit">
            {lines.map((html, i) => (
              <div key={i} className="flex hover:bg-muted/60">
                <span className="sticky left-0 w-12 shrink-0 bg-card pr-3 text-right text-muted-foreground/60 select-none">
                  {i + 1}
                </span>
                <code className="pr-4 whitespace-pre" dangerouslySetInnerHTML={{ __html: html || ' ' }} />
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function size(bytes: number): string {
  if (bytes < 1024) return `${bytes} byte`
  return `${num(Math.round((bytes / 1024) * 10) / 10)} KB`
}
