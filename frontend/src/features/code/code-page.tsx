import { PageShell } from '@/components/page'
import { BrowseView } from './browse-view'
import { DiffView } from './diff-view'

/** #/codice?ref=gen-3&path=src/main.rs to browse, #/codice?diff=gen-3 for what changed. */
export default function CodePage({ params }: { params: URLSearchParams }) {
  const diff = params.get('diff')
  return (
    <PageShell
      title="Codice"
      intro="Il motore di scacchi che l’agente sta scrivendo, in Rust, file per file. Puoi guardare ogni generazione e cosa è cambiato da una all’altra."
    >
      {diff !== null ? <DiffView diff={diff} /> : <BrowseView codeRef={params.get('ref') ?? undefined} path={params.get('path')} />}
    </PageShell>
  )
}
