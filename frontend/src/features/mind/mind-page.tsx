import { ChevronRight } from 'lucide-react'
import type { ReactNode } from 'react'
import { AgentMarkdown } from '@/components/markdown'
import { ErrorNote, LoadingNote, PageShell, StateNote, card } from '@/components/page'
import { useI18n } from '@/i18n/context'
import { LangBadge } from '@/i18n/parts'
import { useMind } from '@/lib/api'
import { cn } from '@/lib/utils'

/** STRATEGY, NOTES and the system prompt are always the English originals, never translated. */
export default function MindPage() {
  const { t, lang, f } = useI18n()
  const mind = useMind()
  return (
    <PageShell title={t('nav.mente')} intro={t('mind.intro')}>
      {mind.isPending ? (
        <LoadingNote what={t('what.mind')} />
      ) : mind.isError ? (
        <ErrorNote what={t('what.mind')} onRetry={() => void mind.refetch()} />
      ) : (
        <>
          <div className="-mt-3 grid gap-1 text-[13px] text-muted-foreground">
            {lang === 'it' && (
              <p className="flex items-center gap-1.5">
                <LangBadge lang="en" />
                {t('mind.english')}
              </p>
            )}
            {mind.data.updated_at && (
              <p>
                {t('mind.updated')} <time dateTime={mind.data.updated_at}>{f.dateTime(mind.data.updated_at)}</time>
              </p>
            )}
          </div>
          <div className="grid items-start gap-4 lg:grid-cols-2">
            <Panel title={t('mind.strategy.title')} hint={t('mind.strategy.hint')}>
              {mind.data.strategy?.trim() ? (
                <AgentMarkdown text={mind.data.strategy} lang="en" />
              ) : (
                <StateNote title={t('mind.strategy.none')} text={t('mind.strategy.noneText')} />
              )}
            </Panel>
            <Panel title={t('mind.notes.title')} hint={t('mind.notes.hint')}>
              {mind.data.notes?.trim() ? (
                <AgentMarkdown text={mind.data.notes} lang="en" />
              ) : (
                <StateNote title={t('mind.notes.none')} text={t('mind.notes.noneText')} />
              )}
            </Panel>
          </div>
          <SystemPrompt text={mind.data.system_prompt} />
        </>
      )}
    </PageShell>
  )
}

function Panel({ title, hint, children }: { title: string; hint: string; children: ReactNode }) {
  return (
    <section className={cn(card, 'grid min-w-0 gap-3')}>
      <header className="grid gap-0.5 border-b pb-3">
        <h2 className="text-[17px] font-semibold tracking-tight">{title}</h2>
        <p className="text-[13px] text-muted-foreground">{hint}</p>
      </header>
      {children}
    </section>
  )
}

function SystemPrompt({ text }: { text: string | null }) {
  const { t } = useI18n()
  return (
    <details className={cn(card, 'group min-w-0 p-0')}>
      <summary className="flex cursor-pointer list-none items-start gap-2.5 rounded-[18px] p-5 hover:bg-muted/50 [&::-webkit-details-marker]:hidden">
        <ChevronRight aria-hidden className="mt-1 size-4 shrink-0 text-muted-foreground transition-transform group-open:rotate-90" />
        <span className="grid gap-0.5">
          <span className="text-[17px] font-semibold tracking-tight">{t('mind.prompt.title')}</span>
          <span className="text-[13px] text-muted-foreground">{t('mind.prompt.hint')}</span>
        </span>
      </summary>
      <div className="border-t px-5 py-4">
        {text?.trim() ? (
          <pre lang="en" className="overflow-x-auto font-mono text-[12.5px] leading-relaxed whitespace-pre-wrap">{text}</pre>
        ) : (
          <StateNote title={t('mind.prompt.none')} />
        )}
      </div>
    </details>
  )
}
