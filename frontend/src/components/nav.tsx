import { type Lang, LANGS, useI18n } from '@/i18n/context'
import { href, type Page, PAGES } from '@/lib/use-route'
import { cn } from '@/lib/utils'

/**
 * The brand, the top-level tabs and the language switch, on every page. Narrow screens scroll
 * the tabs sideways; the brand and the switch stay put.
 */
export function Nav({ current }: { current: Page }) {
  const { t } = useI18n()
  return (
    <nav
      aria-label={t('nav.label')}
      className="sticky top-0 z-20 flex items-center gap-4 border-b bg-background/90 px-4 backdrop-blur sm:px-8"
    >
      <a href={href('diretta')} className="shrink-0 cursor-pointer text-[15px] font-bold tracking-tight">
        darwin-chess
      </a>
      <ul className="-mb-px flex min-w-0 gap-1 overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        {PAGES.map((page) => {
          const active = page === current
          return (
            <li key={page} className="shrink-0">
              <a
                href={href(page)}
                aria-current={active ? 'page' : undefined}
                className={cn(
                  'inline-flex h-11 cursor-pointer items-center border-b-2 px-2.5 text-[14px] font-medium whitespace-nowrap transition-colors',
                  'rounded-t-md focus-visible:ring-2 focus-visible:ring-ring/60 focus-visible:outline-none',
                  active ? 'border-live text-foreground' : 'border-transparent text-muted-foreground hover:text-foreground',
                )}
              >
                {t(`nav.${page}`)}
              </a>
            </li>
          )
        })}
      </ul>
      <LangToggle />
    </nav>
  )
}

const LANG_NAMES: Record<Lang, string> = { it: 'Italiano', en: 'English' }

/** "IT | EN": each button names its language in that language, for whoever needs to switch. */
function LangToggle() {
  const { lang, setLang, t } = useI18n()
  return (
    <div role="group" aria-label={t('nav.language')} className="ml-auto flex shrink-0 items-center font-mono text-[12px] font-medium">
      {LANGS.map((code, i) => (
        <span key={code} className="flex items-center">
          {i > 0 && <span aria-hidden className="px-0.5 text-border">|</span>}
          <button
            type="button"
            lang={code}
            aria-pressed={lang === code}
            aria-label={LANG_NAMES[code]}
            onClick={() => setLang(code)}
            className={cn(
              'h-8 cursor-pointer rounded-md px-1.5 transition-colors focus-visible:ring-2 focus-visible:ring-ring/60 focus-visible:outline-none',
              lang === code ? 'text-foreground' : 'text-muted-foreground hover:text-foreground',
            )}
          >
            {code.toUpperCase()}
          </button>
        </span>
      ))}
    </div>
  )
}
