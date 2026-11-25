import { useEffect, useState } from 'react'

export type Page = 'diretta' | 'evoluzione' | 'codice' | 'mente' | 'laboratorio'

export type Route = { page: Page; params: URLSearchParams }

export const TABS: { page: Page; label: string }[] = [
  { page: 'diretta', label: 'Diretta' },
  { page: 'evoluzione', label: 'Evoluzione' },
  { page: 'codice', label: 'Codice' },
  { page: 'mente', label: 'Mente' },
  { page: 'laboratorio', label: 'Laboratorio' },
]

const PAGES: readonly Page[] = ['evoluzione', 'codice', 'mente', 'laboratorio']

/** "#/codice?ref=gen-3&path=src/main.rs" → codice + its params; anything unknown is the live view. */
function parse(hash: string): Route {
  const [path = '', query = ''] = hash.replace(/^#\/?/, '').split('?', 2)
  const name = path.replace(/\/+$/, '')
  const page = PAGES.find((p) => p === name) ?? 'diretta'
  return { page, params: new URLSearchParams(query) }
}

/** The page in the URL hash: shareable links without any server-side routing. */
export function useRoute(): Route {
  const [hash, setHash] = useState(() => window.location.hash)
  useEffect(() => {
    const onChange = () => setHash(window.location.hash)
    window.addEventListener('hashchange', onChange)
    return () => window.removeEventListener('hashchange', onChange)
  }, [])
  return parse(hash)
}

/** The hash for a page with optional params, empty values dropped: href('codice', { ref: 'gen-3' }). */
export function href(page: Page, params: Record<string, string | null | undefined> = {}): string {
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) if (value) query.set(key, value)
  const base = page === 'diretta' ? '#/' : `#/${page}`
  const tail = query.toString()
  // Slashes in file paths stay readable in a shared link.
  return tail ? `${base}?${tail.replaceAll('%2F', '/')}` : base
}
