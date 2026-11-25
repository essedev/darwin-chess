import { type ReactNode, useEffect, useMemo, useState } from 'react'
import {
  DICTIONARIES,
  type I18n,
  I18nContext,
  type Lang,
  type PluralKey,
  initialLang,
  interpolate,
  isMessageKey,
  saveLang,
} from './context'
import { makeFormat } from './format'
import type { MessageKey } from './it'

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(initialLang)

  useEffect(() => {
    document.documentElement.lang = lang
  }, [lang])

  const value = useMemo<I18n>(() => {
    const dictionary = DICTIONARIES[lang]
    const f = makeFormat(lang)
    const t = (key: MessageKey, params?: Parameters<I18n['t']>[1]) => interpolate(dictionary[key], params)
    return {
      lang,
      setLang: (next: Lang) => {
        saveLang(next)
        setLangState(next)
      },
      t,
      tn: (key: PluralKey, count: number, params) =>
        t(`${key}.${count === 1 ? 'one' : 'other'}` as MessageKey, { n: f.num(count), ...params }),
      label: (group, raw) => {
        const key = `${group}.${raw}`
        return isMessageKey(dictionary, key) ? dictionary[key] : raw
      },
      f,
    }
  }, [lang])

  return <I18nContext value={value}>{children}</I18nContext>
}
