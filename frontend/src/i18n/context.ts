import { createContext, useContext } from 'react'
import { en } from './en'
import type { Format } from './format'
import { it, type MessageKey, type Messages } from './it'

export type Lang = 'it' | 'en'

export const LANGS: readonly Lang[] = ['it', 'en']

export const DICTIONARIES: Record<Lang, Messages> = { it, en }

export type Params = Record<string, string | number>

/** The keys that come in a `.one` / `.other` pair, without the suffix. */
export type PluralKey = {
  [K in MessageKey]: K extends `${infer Base}.one` ? (`${Base}.other` extends MessageKey ? Base : never) : never
}[MessageKey]

export type I18n = {
  lang: Lang
  setLang: (lang: Lang) => void
  /** The text for `key`, with `{name}` placeholders filled from `params`. */
  t: (key: MessageKey, params?: Params) => string
  /** The `.one` or `.other` form for `count`; `{n}` is the count, formatted. */
  tn: (key: PluralKey, count: number, params?: Params) => string
  /** A label looked up from data (a status, a gate); unknown values come back as they are. */
  label: (group: string, value: string) => string
  f: Format
}

export const I18nContext = createContext<I18n | null>(null)

export function useI18n(): I18n {
  const value = useContext(I18nContext)
  if (!value) throw new Error('useI18n outside LanguageProvider')
  return value
}

export const useT = () => useI18n().t

export function interpolate(text: string, params?: Params): string {
  if (!params) return text
  return text.replace(/\{(\w+)\}/g, (whole, name: string) => (name in params ? String(params[name]) : whole))
}

export function isMessageKey(dictionary: Messages, key: string): key is MessageKey {
  return Object.hasOwn(dictionary, key)
}

const STORAGE_KEY = 'darwin-chess.lang'

/** The saved choice, else the browser's language: Italian for it-*, English for the rest. */
export function initialLang(): Lang {
  try {
    const saved = window.localStorage.getItem(STORAGE_KEY)
    if (saved === 'it' || saved === 'en') return saved
  } catch {
    // Storage blocked (private mode, disabled cookies): fall back to the browser language.
  }
  return navigator.language.toLowerCase().startsWith('it') ? 'it' : 'en'
}

export function saveLang(lang: Lang) {
  try {
    window.localStorage.setItem(STORAGE_KEY, lang)
  } catch {
    // Not persisted: the choice still holds until the page is reloaded.
  }
}

/** Agent-written texts and the changelog: the visitor's language when it exists, else the other one. */
export type Picked = { text: string; lang: Lang; fallback: boolean }

export function pickText(lang: Lang, texts: Partial<Record<Lang, string | null | undefined>>): Picked | null {
  const own = texts[lang]?.trim()
  if (own) return { text: own, lang, fallback: false }
  const otherLang: Lang = lang === 'it' ? 'en' : 'it'
  const other = texts[otherLang]?.trim()
  return other ? { text: other, lang: otherLang, fallback: true } : null
}
