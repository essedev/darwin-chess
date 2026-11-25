import { FolderTree } from 'lucide-react'
import { useState } from 'react'
import { ErrorNote, LoadingNote, StateNote, card } from '@/components/page'
import { isClientError, useCodeTree } from '@/lib/api'
import { href } from '@/lib/use-route'
import { cn } from '@/lib/utils'
import { FileTree } from './file-tree'
import { FileViewer } from './file-viewer'
import { RefSelect } from './ref-select'

const DEFAULT_FILES = ['src/main.rs', 'Cargo.toml', 'README.md']

/** The genome at one version: tree on the left (above, on mobile), the chosen file on the right. */
export function BrowseView({ codeRef, path }: { codeRef: string | undefined; path: string | null }) {
  const tree = useCodeTree(codeRef)
  const [treeOpen, setTreeOpen] = useState(false)
  if (tree.isPending) return <LoadingNote what="il codice" />
  if (tree.isError) {
    return isClientError(tree.error) ? (
      <StateNote title="Questa versione non esiste" text={<a className="cursor-pointer underline" href={href('codice')}>Guarda il codice del campione</a>} />
    ) : (
      <ErrorNote what="il codice" onRetry={() => void tree.refetch()} />
    )
  }
  const { commit, files } = tree.data
  const paths = files.map((f) => f.path)
  const shown = path ?? DEFAULT_FILES.find((f) => paths.includes(f)) ?? paths[0] ?? null
  const linkTo = (p: string) => href('codice', { ref: codeRef, path: p })
  return (
    <div className="grid gap-4">
      <RefSelect current={codeRef} commit={commit} generation={tree.data.generation} path={path} />
      {files.length === 0 ? (
        <StateNote title="Nessun file in questa versione" className={card} />
      ) : (
        <div className="grid items-start gap-4 lg:grid-cols-[280px_minmax(0,1fr)]">
          <aside className={cn(card, 'min-w-0 p-2 lg:sticky lg:top-16 lg:max-h-[calc(100svh-5.5rem)] lg:overflow-y-auto')}>
            <button
              type="button"
              aria-expanded={treeOpen}
              onClick={() => setTreeOpen((open) => !open)}
              className="flex w-full cursor-pointer items-center gap-2 rounded-md px-2 py-2 text-left text-[13px] font-medium hover:bg-muted lg:hidden"
            >
              <FolderTree aria-hidden className="size-4 shrink-0 text-muted-foreground" />
              <span className="min-w-0 flex-1 truncate">{treeOpen ? 'Nascondi i file' : `File: ${shown ?? 'nessuno'}`}</span>
              <span className="text-[12px] text-muted-foreground">{files.length}</span>
            </button>
            <div className={cn(treeOpen ? 'block' : 'hidden', 'pt-1 lg:block lg:pt-0')}>
              <FileTree paths={paths} selected={shown} linkTo={linkTo} onPick={() => setTreeOpen(false)} />
            </div>
          </aside>
          <section className={cn(card, 'min-w-0 overflow-hidden p-0')}>
            <FileViewer commit={commit} path={shown} />
          </section>
        </div>
      )}
    </div>
  )
}
