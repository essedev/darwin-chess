import type { Lang } from './context'

const LOCALES: Record<Lang, string> = { it: 'it-IT', en: 'en-GB' }

/** Numbers, money and dates in the visitor's language; the currency is always USD. */
export function makeFormat(lang: Lang) {
  const locale = LOCALES[lang]
  // en-GB would print "US$": the plain symbol reads better, Italian keeps its "USD".
  const currencyDisplay = lang === 'en' ? 'narrowSymbol' : 'symbol'
  const usd = new Intl.NumberFormat(locale, { style: 'currency', currency: 'USD', currencyDisplay })
  const cents = new Intl.NumberFormat(locale, { style: 'currency', currency: 'USD', currencyDisplay, maximumFractionDigits: 3 })
  const decimal = new Intl.NumberFormat(locale, { maximumFractionDigits: 2 })
  const compact = new Intl.NumberFormat(locale, { notation: 'compact', maximumFractionDigits: 1 })
  const num = (value: number) => decimal.format(value)
  return {
    locale,
    money: (value: number) => usd.format(value),
    /** Small sums keep a third decimal: one attempt often costs a fraction of a cent. */
    preciseMoney: (value: number) => (value < 1 ? cents.format(value) : usd.format(value)),
    num,
    compact: (value: number) => compact.format(value),
    /** "+34", "−12" (true minus sign), "0": a gain or loss of Elo. */
    signed: (value: number) => {
      const rounded = Math.round(value)
      if (rounded === 0) return '0'
      return rounded > 0 ? `+${num(rounded)}` : `−${num(-rounded)}`
    },
    /** "12 nov, 14:30" / "12 Nov, 14:30" in the visitor's time zone. */
    dateTime: (iso: string) =>
      new Date(iso).toLocaleString(locale, { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }),
    /** "12 novembre 2026" / "12 November 2026". */
    longDate: (iso: string) => new Date(iso).toLocaleDateString(locale, { day: 'numeric', month: 'long', year: 'numeric' }),
    /** "12 nov" / "12 Nov". */
    shortDate: (iso: string) => new Date(iso).toLocaleDateString(locale, { day: 'numeric', month: 'short' }),
    /** "14:30". */
    time: (iso: string) => new Date(iso).toLocaleTimeString(locale, { hour: '2-digit', minute: '2-digit' }),
  }
}

export type Format = ReturnType<typeof makeFormat>
