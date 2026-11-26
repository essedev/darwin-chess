import { ErrorNote, LoadingNote, StateNote, card } from '@/components/page'
import { type I18n, useI18n } from '@/i18n/context'
import { isClientError, type DiffFile, useCodeDiff } from '@/lib/api'
import { href } from '@/lib/use-route'
import { cn } from '@/lib/utils'

/** git's one-letter statuses, as the words the dictionaries know under `fileStatus.*`. */
const STATUS_WORD: Record<string, string> = { A: 'added', M: 'modified', D: 'deleted', R: 'renamed' }

/** "gen-3" or "exp-12" from the link; anything else is not a diff we can ask for. */
function parse({ t }: I18n, diff: string): { query: string; title: string; ref: string; session: string | null } | null {
  const match = /^(gen|exp)-(\d+)$/.exec(diff)
  if (!match) return null
  const [, kind, id] = match
  return kind === 'gen'
    ? { query: `gen=${id}`, title: t('diff.titleGen', { id: id ?? '' }), ref: diff, session: null }
    : { query: `exp=${id}`, title: t('diff.titleExp', { id: id ?? '' }), ref: diff, session: id ?? null }
}

export function DiffView({ diff }: { diff: string }) {
  const i18n = useI18n()
  const { t } = i18n
  const spec = parse(i18n, diff)
  const result = useCodeDiff(spec?.query ?? null)
  if (!spec) return <StateNote title={t('diff.invalid.title')} text={t('diff.invalid.text')} className={card} />
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
          {t('diff.browse')}
        </a>
        {spec.session && (
          <a href={href('sessione', { id: spec.session })} className="cursor-pointer text-[13px] font-medium text-live underline-offset-4 hover:underline">
            {t('diff.session', { id: spec.session })}
          </a>
        )}
      </div>
      {result.isPending ? (
        <LoadingNote what={t('what.changes')} />
      ) : result.isError ? (
        isClientError(result.error) ? (
          <StateNote title={t('diff.unavailable.title')} text={t('diff.unavailable.text')} className={card} />
        ) : (
          <ErrorNote what={t('what.changes')} onRetry={() => void result.refetch()} />
        )
      ) : result.data.files.length === 0 ? (
        <StateNote title={t('diff.none')} className={card} />
      ) : (
        <DiffFiles files={result.data.files} />
      )}
    </div>
  )
}

function DiffFiles({ files }: { files: DiffFile[] }) {
  const { t, tn, label, f } = useI18n()
  const additions = files.reduce((sum, f) => sum + f.additions, 0)
  const deletions = files.reduce((sum, f) => sum + f.deletions, 0)
  const openByDefault = files.length <= 8
  return (
    <>
      <p className="text-[13px] text-muted-foreground">
        {tn('count.files', files.length)} ·{' '}
        <span className="font-mono text-good">+{f.num(additions)}</span> <span className="font-mono text-bad">−{f.num(deletions)}</span>{' '}
        {t('diff.lines')}
      </p>
      <div className="grid gap-3">
        {files.map((file) => (
          <details key={file.path} open={openByDefault} className={cn(card, 'group min-w-0 overflow-hidden p-0')}>
            <summary className="flex cursor-pointer flex-wrap items-baseline gap-x-3 gap-y-1 px-4 py-3 hover:bg-muted/60">
              <span className="rounded-full bg-muted px-2 py-px text-[11px] font-medium text-muted-foreground">
                {label('fileStatus', STATUS_WORD[file.status] ?? file.status)}
              </span>
              <span className="min-w-0 flex-1 font-mono text-[13px] font-medium break-all">{file.path}</span>
              <span className="font-mono text-[12px]">
                <span className="text-good">+{f.num(file.additions)}</span> <span className="text-bad">−{f.num(file.deletions)}</span>
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
  const { t } = useI18n()
  if (!patch) return <p className="border-t px-4 py-3 text-[13px] text-muted-foreground">{t('diff.noPatch')}</p>
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
