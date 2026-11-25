import { href, type Page, TABS } from '@/lib/use-route'
import { cn } from '@/lib/utils'


/**
 * Top-level tabs. On the live view the brand is already in its own top bar, so here it
 * shows only on the other pages. Narrow screens scroll the tabs sideways.
 */
export function Nav({ current }: { current: Page }) {
  return (
    <nav
      aria-label="Sezioni"
      className="sticky top-0 z-20 flex items-center gap-4 border-b bg-background/90 px-4 backdrop-blur sm:px-8"
    >
      {current !== 'diretta' && (
        <a href={href('diretta')} className="hidden shrink-0 cursor-pointer text-[15px] font-bold tracking-tight sm:block">
          darwin-chess
        </a>
      )}
      <ul className="-mb-px flex min-w-0 gap-1 overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        {TABS.map((tab) => {
          const active = tab.page === current
          return (
            <li key={tab.page} className="shrink-0">
              <a
                href={href(tab.page)}
                aria-current={active ? 'page' : undefined}
                className={cn(
                  'inline-flex h-11 cursor-pointer items-center border-b-2 px-2.5 text-[14px] font-medium whitespace-nowrap transition-colors',
                  'rounded-t-md focus-visible:ring-2 focus-visible:ring-ring/60 focus-visible:outline-none',
                  active ? 'border-live text-foreground' : 'border-transparent text-muted-foreground hover:text-foreground',
                )}
              >
                {tab.label}
              </a>
            </li>
          )
        })}
      </ul>
    </nav>
  )
}
