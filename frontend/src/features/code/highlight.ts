import hljs from 'highlight.js/lib/core'
import ini from 'highlight.js/lib/languages/ini'
import json from 'highlight.js/lib/languages/json'
import markdown from 'highlight.js/lib/languages/markdown'
import python from 'highlight.js/lib/languages/python'
import rust from 'highlight.js/lib/languages/rust'

// Only the languages of the genome: the full highlight.js bundle is ten times larger.
hljs.registerLanguage('rust', rust)
hljs.registerLanguage('toml', ini)
hljs.registerLanguage('markdown', markdown)
hljs.registerLanguage('python', python)
hljs.registerLanguage('json', json)

const BY_EXTENSION: Record<string, string> = {
  rs: 'rust',
  toml: 'toml',
  md: 'markdown',
  py: 'python',
  json: 'json',
}

const escapeHtml = (text: string) => text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')

/**
 * The file as one escaped HTML string per line. highlight.js escapes the source itself; a
 * token that spans several lines (a block comment) is closed and reopened on each line.
 */
export function highlightLines(content: string, path: string): string[] {
  const language = BY_EXTENSION[path.split('.').pop()?.toLowerCase() ?? '']
  const html = language ? hljs.highlight(content, { language, ignoreIllegals: true }).value : escapeHtml(content)
  const lines = splitLines(html)
  if (content.endsWith('\n')) lines.pop()
  return lines
}

function splitLines(html: string): string[] {
  const lines: string[] = []
  const open: string[] = []
  let current = ''
  let last = 0
  for (const match of html.matchAll(/<span class="[^"]*">|<\/span>|\n/g)) {
    current += html.slice(last, match.index)
    last = match.index + match[0].length
    if (match[0] === '\n') {
      lines.push(current + '</span>'.repeat(open.length))
      current = open.join('')
    } else {
      if (match[0] === '</span>') open.pop()
      else open.push(match[0])
      current += match[0]
    }
  }
  lines.push(current + html.slice(last))
  return lines
}
