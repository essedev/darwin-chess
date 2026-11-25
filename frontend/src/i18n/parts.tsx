import { Fragment, type ReactNode } from 'react'
import { cn } from '@/lib/utils'
import { type Lang, useI18n } from './context'

/**
 * A translated sentence with styled pieces inside: `text` keeps its `{name}` placeholders
 * (call `t(key)` without params) and each one is replaced by the node in `values`.
 */
export function Rich({ text, values }: { text: string; values: Record<string, ReactNode> }) {
  const parts = text.split(/(\{\w+\})/)
  return (
    <>
      {parts.map((part, i) => {
        const name = /^\{(\w+)\}$/.exec(part)?.[1]
        return <Fragment key={i}>{name !== undefined && name in values ? values[name] : part}</Fragment>
      })}
    </>
  )
}

/**
 * A quiet tag on a text shown in its original language because no translation exists:
 * "EN" on an agent's hypothesis in the Italian dashboard, "IT" on the changelog in the English one.
 */
export function LangBadge({ lang, className }: { lang: Lang; className?: string }) {
  const { t } = useI18n()
  const title = lang === 'en' ? t('badge.en') : t('badge.it')
  return (
    <abbr
      title={title}
      className={cn(
        'inline-flex h-4 flex-none items-center rounded-[4px] px-1 align-[1px] font-mono text-[10px] leading-none font-medium text-muted-foreground no-underline shadow-[inset_0_0_0_1px_var(--border)]',
        className,
      )}
    >
      {lang.toUpperCase()}
    </abbr>
  )
}
