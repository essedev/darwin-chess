import { type ReactNode, useEffect, useRef, useState } from 'react'
import { useT } from '@/i18n/context'
import { cn } from '@/lib/utils'
import { Board } from './board'

export const START = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1'

/** Board with the black player above, the white one below and the moves beside it. */
export function GameFrame(props: {
  top: ReactNode
  bottom: ReactNode
  fen: string
  lastMove: string | null
  san: string[]
  startPly: number
}) {
  return (
    <div className="grid w-full min-w-0 grid-cols-1 gap-x-4 gap-y-2.5 lg:grid-cols-[minmax(0,1fr)_130px]">
      {props.top}
      <span className="hidden lg:block" />
      <div className="min-w-0">
        <Board fen={props.fen} lastMove={props.lastMove} />
      </div>
      <Moves san={props.san} startPly={props.startPly} />
      {props.bottom}
    </div>
  )
}

export function Player(props: {
  colour: 'white' | 'black'
  label: string
  detail: string
  badge?: string | null
  aside?: ReactNode
}) {
  return (
    <div className="flex min-h-10 items-center gap-3 px-0.5">
      <span className={`size-3 flex-none rounded-full shadow-[0_0_0_1.5px_var(--border)] ${props.colour === 'white' ? 'bg-[#fbfaf7]' : 'bg-[#16140f]'}`} />
      <span className="min-w-0">
        <span className="flex items-center gap-1.5">
          {props.badge && (
            <span className="flex-none rounded-[5px] bg-live/15 px-1.5 py-px font-mono text-[10px] font-semibold text-live">{props.badge}</span>
          )}
          <b className="block truncate text-[15px] font-semibold">{props.label}</b>
        </span>
        <span className="block text-xs text-muted-foreground">{props.detail}</span>
      </span>
      {props.aside && <span className="ml-auto text-right">{props.aside}</span>}
    </div>
  )
}

/** Games won so far in the match, shown beside an arena player. */
export function Points({ value }: { value: number }) {
  const t = useT()
  return (
    <>
      <b className="block font-mono text-xl leading-none font-medium tabular-nums">{value}</b>
      <span className="text-xs text-muted-foreground">{t('arena.won')}</span>
    </>
  )
}

function Moves({ san, startPly }: { san: string[]; startPly: number }) {
  const t = useT()
  const box = useRef<HTMLDivElement>(null)
  const [hidden, setHidden] = useState(false)
  useEffect(() => {
    const el = box.current
    if (!el) return
    el.scrollTo({ top: el.scrollHeight, left: el.scrollWidth })
    setHidden(el.scrollHeight > el.clientHeight + 1 || el.scrollWidth > el.clientWidth + 1)
  }, [san.length])
  const plies = startPly % 2 === 1 ? ['…', ...san] : san
  const rows = []
  for (let i = 0; i < plies.length; i += 2) rows.push([plies[i], plies[i + 1]])
  const firstMove = Math.floor(startPly / 2) + 1
  return (
    // On wide screens the list never sizes the row: it fills the board's height and scrolls,
    // so a long game does not push the layout around.
    <div className="relative min-w-0 lg:min-h-0">
      <div
        ref={box}
        className={cn(
          'flex gap-0.5 overflow-x-auto font-mono text-xs tabular-nums [scrollbar-width:none]',
          'lg:absolute lg:inset-0 lg:block lg:overflow-x-hidden lg:overflow-y-auto',
          hidden &&
            '[mask-image:linear-gradient(to_right,transparent,#000_32px)] lg:[mask-image:linear-gradient(to_bottom,transparent,#000_56px)]',
        )}
      >
        {rows.length === 0 && <span className="text-muted-foreground">{t('arena.noMoves')}</span>}
        {rows.map(([white, black], i) => (
          <div key={i} className="grid h-[26px] flex-none grid-cols-[26px_1fr_1fr] items-center">
            <span className="text-[11px] text-muted-foreground">{firstMove + i}</span>
            <span className={cn('rounded-md px-1.5 py-1', i === rows.length - 1 && !black && 'bg-live/22 font-medium')}>{white}</span>
            <span className={cn('rounded-md px-1.5 py-1', i === rows.length - 1 && black && 'bg-live/22 font-medium')}>{black ?? ''}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
