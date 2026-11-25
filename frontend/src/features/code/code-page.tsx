import { PageShell } from '@/components/page'
import { useT } from '@/i18n/context'
import { BrowseView } from './browse-view'
import { DiffView } from './diff-view'

/** #/codice?ref=gen-3&path=src/main.rs to browse, #/codice?diff=gen-3 for what changed. */
export default function CodePage({ params }: { params: URLSearchParams }) {
  const t = useT()
  const diff = params.get('diff')
  return (
    <PageShell title={t('nav.codice')} intro={t('code.intro')}>
      {diff !== null ? <DiffView diff={diff} /> : <BrowseView codeRef={params.get('ref') ?? undefined} path={params.get('path')} />}
    </PageShell>
  )
}
