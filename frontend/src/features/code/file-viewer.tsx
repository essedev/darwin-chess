import { useMemo } from 'react'
import { ErrorNote, LoadingNote, StateNote } from '@/components/page'
import { type I18n, useI18n } from '@/i18n/context'
import { isClientError, type CodeFile, useCodeFile } from '@/lib/api'
import { highlightLines } from './highlight'

/** One file of a commit, with line numbers and syntax colours. */
export function FileViewer({ commit, path }: { commit: string; path: string | null }) {
  const { t } = useI18n()
  const file = useCodeFile(commit, path)
  if (path === null) return <StateNote title={t('file.choose.title')} text={t('file.choose.text')} />
  if (file.isPending) return <LoadingNote what={t('what.file')} />
  if (file.isError) {
    return isClientError(file.error) ? (
      <StateNote title={t('file.missing.title')} text={t('file.missing.text')} />
    ) : (
      <ErrorNote what={t('what.file')} onRetry={() => void file.refetch()} />
    )
  }
  return <FileBody file={file.data} />
}

function FileBody({ file }: { file: CodeFile }) {
  const i18n = useI18n()
  const { t, tn } = i18n
  const lines = useMemo(
    () => (file.content ? highlightLines(file.content, file.path) : []),
    [file.content, file.path],
  )
  return (
    <div className="grid min-w-0">
      <p className="flex flex-wrap items-baseline gap-x-3 border-b px-4 py-3 text-[12px] text-muted-foreground">
        <span className="font-mono text-[13px] font-medium break-all text-foreground">{file.path}</span>
        <span>{size(i18n, file.size)}</span>
        {lines.length > 0 && <span>{tn('count.lines', lines.length)}</span>}
      </p>
      {file.truncated && (
        <p className="border-b bg-live/8 px-4 py-2 text-[12px] text-muted-foreground">
          {t('file.truncated')}
        </p>
      )}
      {file.binary ? (
        <StateNote title={t('file.binary')} />
      ) : lines.length === 0 ? (
        <StateNote title={t('file.empty')} />
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

function size({ t, f }: I18n, bytes: number): string {
  if (bytes < 1024) return t('file.bytes', { n: f.num(bytes) })
  return `${f.num(Math.round((bytes / 1024) * 10) / 10)} KB`
}
