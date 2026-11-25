import { ChevronRight } from 'lucide-react'
import { useMemo, useState } from 'react'
import { cn } from '@/lib/utils'

type Folder = { name: string; path: string; folders: Folder[]; files: { name: string; path: string }[] }

/** Nested folders from flat paths; folders first, then files, both alphabetical. */
function buildTree(paths: string[]): Folder {
  const root: Folder = { name: '', path: '', folders: [], files: [] }
  for (const path of paths) {
    const parts = path.split('/')
    let folder = root
    for (const part of parts.slice(0, -1)) {
      const sub = `${folder.path}${part}/`
      let next = folder.folders.find((f) => f.path === sub)
      if (!next) {
        next = { name: part, path: sub, folders: [], files: [] }
        folder.folders.push(next)
      }
      folder = next
    }
    folder.files.push({ name: parts.at(-1) ?? path, path })
  }
  const sort = (folder: Folder) => {
    folder.folders.sort((a, b) => a.name.localeCompare(b.name))
    folder.files.sort((a, b) => a.name.localeCompare(b.name))
    folder.folders.forEach(sort)
  }
  sort(root)
  return root
}

export function FileTree(props: { paths: string[]; selected: string | null; linkTo: (path: string) => string; onPick?: () => void }) {
  const root = useMemo(() => buildTree(props.paths), [props.paths])
  const [closed, setClosed] = useState<ReadonlySet<string>>(new Set())
  const toggle = (path: string) =>
    setClosed((previous) => {
      const next = new Set(previous)
      if (!next.delete(path)) next.add(path)
      return next
    })
  return (
    <ul className="grid font-mono text-[12.5px]">
      <Entries folder={root} depth={0} closed={closed} toggle={toggle} {...props} />
    </ul>
  )
}

function Entries(props: {
  folder: Folder
  depth: number
  closed: ReadonlySet<string>
  toggle: (path: string) => void
  selected: string | null
  linkTo: (path: string) => string
  onPick?: () => void
}) {
  const { folder, depth } = props
  const indent = { paddingLeft: `${depth * 14 + 8}px` }
  return (
    <>
      {folder.folders.map((sub) => {
        const open = !props.closed.has(sub.path)
        return (
          <li key={sub.path}>
            <button
              type="button"
              aria-expanded={open}
              onClick={() => props.toggle(sub.path)}
              style={indent}
              className="flex w-full cursor-pointer items-center gap-1 rounded-md py-1 pr-2 text-left hover:bg-muted"
            >
              <ChevronRight aria-hidden className={cn('size-3.5 shrink-0 text-muted-foreground transition-transform', open && 'rotate-90')} />
              <span className="truncate">{sub.name}/</span>
            </button>
            {open && (
              <ul>
                <Entries {...props} folder={sub} depth={depth + 1} />
              </ul>
            )}
          </li>
        )
      })}
      {folder.files.map((file) => {
        const active = file.path === props.selected
        return (
          <li key={file.path}>
            <a
              href={props.linkTo(file.path)}
              onClick={props.onPick}
              aria-current={active ? 'true' : undefined}
              style={{ paddingLeft: `${depth * 14 + 26}px` }}
              className={cn(
                'block cursor-pointer truncate rounded-md py-1 pr-2',
                active ? 'bg-live/12 font-medium text-live' : 'hover:bg-muted',
              )}
            >
              {file.name}
            </a>
          </li>
        )
      })}
    </>
  )
}
