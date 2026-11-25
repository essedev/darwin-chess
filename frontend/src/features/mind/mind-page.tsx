import { ChevronRight } from 'lucide-react'
import { type ReactNode, useState } from 'react'
import { AgentMarkdown } from '@/components/markdown'
import { ErrorNote, LoadingNote, PageShell, StateNote, card } from '@/components/page'
import { useI18n } from '@/i18n/context'
import { LangBadge } from '@/i18n/parts'
import { useMind } from '@/lib/api'
import { cn } from '@/lib/utils'

/**
 * STRATEGY, NOTES and the system prompt: in Italian when the current version has been
 * translated, with the English original a click away; else the original, marked.
 */
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
            {lang === 'it' && <p>{t('mind.english')}</p>}
            {mind.data.updated_at && (
              <p>
                {t('mind.updated')} <time dateTime={mind.data.updated_at}>{f.dateTime(mind.data.updated_at)}</time>
              </p>
            )}
          </div>
          <div className="grid items-start gap-4 lg:grid-cols-2">
            <Panel title={t('mind.strategy.title')} hint={t('mind.strategy.hint')}>
              {mind.data.strategy?.trim() ? (
                <Bilingual original={mind.data.strategy} italian={mind.data.strategy_it}>
                  {(text, textLang) => <AgentMarkdown text={text} lang={textLang} />}
                </Bilingual>
              ) : (
                <StateNote title={t('mind.strategy.none')} text={t('mind.strategy.noneText')} />
              )}
            </Panel>
            <Panel title={t('mind.notes.title')} hint={t('mind.notes.hint')}>
              {mind.data.notes?.trim() ? (
                <Bilingual original={mind.data.notes} italian={mind.data.notes_it}>
                  {(text, textLang) => <AgentMarkdown text={text} lang={textLang} />}
                </Bilingual>
              ) : (
                <StateNote title={t('mind.notes.none')} text={t('mind.notes.noneText')} />
              )}
            </Panel>
          </div>
          <SystemPrompt text={mind.data.system_prompt} italian={mind.data.system_prompt_it} />
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

function SystemPrompt({ text, italian }: { text: string | null; italian?: string | null }) {
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
          <Bilingual original={text} italian={italian}>
            {(shown, shownLang) => (
              <pre lang={shownLang} className="overflow-x-auto font-mono text-[12.5px] leading-relaxed whitespace-pre-wrap">{shown}</pre>
            )}
          </Bilingual>
        ) : (
          <StateNote title={t('mind.prompt.none')} />
        )}
      </div>
    </details>
  )
}

/**
 * The Italian of an English text when the visitor reads in Italian and it exists, with a
 * switch to the original; otherwise the original, marked as such.
 */
function Bilingual(props: {
  original: string
  italian?: string | null
  children: (text: string, lang: 'it' | 'en') => ReactNode
}) {
  const { t, lang } = useI18n()
  const [showOriginal, setShowOriginal] = useState(false)
  if (lang !== 'it') return <>{props.children(props.original, 'en')}</>
  if (!props.italian) {
    return (
      <div className="grid gap-2">
        <p className="flex items-center gap-1.5 text-[12px] text-muted-foreground">
          <LangBadge lang="en" /> {t('mind.translationPending')}
        </p>
        {props.children(props.original, 'en')}
      </div>
    )
  }
  return (
    <div className="grid gap-2">
      <button
        type="button"
        aria-pressed={showOriginal}
        onClick={() => setShowOriginal((value) => !value)}
        className="w-fit cursor-pointer text-[12px] font-medium text-live underline-offset-4 hover:underline"
      >
        {showOriginal ? t('mind.showItalian') : t('mind.showOriginal')}
      </button>
      {showOriginal ? props.children(props.original, 'en') : props.children(props.italian, 'it')}
    </div>
  )
}
