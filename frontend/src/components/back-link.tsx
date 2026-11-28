import { ChevronLeft } from 'lucide-react'
import { type I18n, useI18n } from '@/i18n/context'
import { href, type Page, type Route, useCameFrom } from '@/lib/use-route'

/**
 * Back to where the visitor came from, filters included ("‹ Partite"); on a page opened from
 * a link, to `fallback`, the page it belongs to.
 */
export function BackLink({ fallback }: { fallback: Page }) {
  const { t } = useI18n()
  const from = useCameFrom()
  const target = from?.hash ?? href(fallback)
  const name = from ? pageName(t, from.route) : t(`nav.${fallback}`)
  return (
    <a
      href={target}
      aria-label={t('back.to', { page: name })}
      className="-ml-1 inline-flex h-7 w-fit cursor-pointer items-center gap-0.5 rounded-md pr-2 pl-0.5 text-[13px] font-medium text-muted-foreground transition-colors hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/60 focus-visible:outline-none"
    >
      <ChevronLeft aria-hidden className="size-4" />
      {name}
    </a>
  )
}

function pageName(t: I18n['t'], route: Route): string {
  const id = route.params.get('id')
  if (route.page === 'sessione' && id) return t('session.title', { id })
  return t(`nav.${route.page}`)
}
