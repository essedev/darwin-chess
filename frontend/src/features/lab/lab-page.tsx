import { ExternalLink } from 'lucide-react'
import { AgentMarkdown } from '@/components/markdown'
import { ErrorNote, LoadingNote, PageShell, card } from '@/components/page'
import { pickText, useI18n } from '@/i18n/context'
import { LangBadge } from '@/i18n/parts'
import { type Lab, useLab } from '@/lib/api'
import { cn } from '@/lib/utils'
import { CostPerGeneration, LabNumbers } from './lab-numbers'

const LINKS = [
  { href: 'https://lichess.org/@/darwin-chess-bot', key: 'lab.link.bot' },
  { href: 'https://esse.dev', key: 'lab.link.author' },
] as const

export default function LabPage() {
  const { t, f } = useI18n()
  const lab = useLab()
  return (
    <PageShell title={t('nav.laboratorio')} intro={t('lab.intro')}>
      <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <HowItWorks />
        {lab.isPending ? (
          <LoadingNote what={t('what.numbers')} />
        ) : lab.isError ? (
          <ErrorNote what={t('what.numbers')} onRetry={() => void lab.refetch()} />
        ) : (
          <CostPerGeneration rows={lab.data.cost_per_generation} />
        )}
      </div>
      {lab.data && (
        <>
          <section aria-labelledby="numbers" className="grid gap-3">
            <h2 id="numbers" className="text-[19px] font-semibold tracking-tight">{t('lab.numbers')}</h2>
            {lab.data.started_at && (
              <p className="-mt-1 text-[13px] text-muted-foreground">{t('lab.since', { date: f.longDate(lab.data.started_at) })}</p>
            )}
            <LabNumbers totals={lab.data.totals} />
          </section>
          <Changelog lab={lab.data} />
        </>
      )}
      <ul className="flex flex-wrap gap-x-6 gap-y-2 text-[14px]">
        {LINKS.map((link) => (
          <li key={link.href}>
            <a href={link.href} target="_blank" rel="noopener" className="inline-flex cursor-pointer items-center gap-1.5 font-medium text-live underline-offset-4 hover:underline">
              {t(link.key)}
              <ExternalLink aria-hidden className="size-3.5" />
            </a>
          </li>
        ))}
      </ul>
    </PageShell>
  )
}

/** The changelog is written in Italian; the English one comes from `changelog_en` when the API has it. */
function Changelog({ lab }: { lab: Lab }) {
  const { t, lang } = useI18n()
  const changelog = pickText(lang, { it: lab.changelog, en: lab.changelog_en })
  return (
    <section className={cn(card, 'grid min-w-0 gap-3')}>
      <h2 className="flex items-center gap-2 text-[17px] font-semibold tracking-tight">
        {t('lab.changelog')}
        {changelog?.fallback && <LangBadge lang={changelog.lang} />}
      </h2>
      {changelog ? (
        <AgentMarkdown text={withoutTitle(changelog.text)} lang={changelog.lang} />
      ) : (
        <p className="py-4 text-center text-[14px] text-muted-foreground">{t('lab.noChangelog')}</p>
      )}
    </section>
  )
}

function HowItWorks() {
  const { t } = useI18n()
  return (
    <section className={cn(card, 'grid min-w-0 gap-3 text-[15px] leading-relaxed text-pretty')}>
      <h2 className="text-[17px] font-semibold tracking-tight">{t('lab.how.title')}</h2>
      <p>{t('lab.how.p1')}</p>
      <p>{t('lab.how.p2')}</p>
      <p>{t('lab.how.p3')}</p>
      <p className="text-muted-foreground">{t('lab.how.p4')}</p>
    </section>
  )
}

/** The changelog opens with its own "# Changelog" title: the card already has one. */
function withoutTitle(markdown: string): string {
  return markdown.replace(/^\s*#\s[^\n]*\n/, '')
}
