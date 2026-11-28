import { ArrowLeft, ArrowRight, ChevronFirst, ChevronLast, ChevronLeft, ChevronRight, ExternalLink } from 'lucide-react'
import { type ReactNode, useEffect, useRef, useState } from 'react'
import { BackLink } from '@/components/back-link'
import { ErrorNote, LoadingNote, StateNote, card } from '@/components/page'
import { Panel } from '@/components/panel'
import { Board } from '@/features/live/board'
import { RESULT_TONE } from '@/features/live/format'
import { Player } from '@/features/live/game-parts'
import { type I18n, pickText, useI18n } from '@/i18n/context'
import type { MessageKey } from '@/i18n/it'
import { isClientError, type GameMove, type LichessGameDetail, type SideReview, useLichessGame } from '@/lib/api'
import { href } from '@/lib/use-route'
import { cn } from '@/lib/utils'
import { EvalChart } from './eval-chart'
import { JUDGEMENTS, MARK, MARK_TONE, moveNumber, pawns } from './review'

const ID = /^[A-Za-z0-9]{1,16}$/

/**
 * One Lichess game of the bot, move by move: the board with our engine at the bottom, the
 * evaluation curve, the moves with their judgements, the move where the game turned, each
 * side's mistakes and the commentary.
 */
export default function GamePage({ params }: { params: URLSearchParams }) {
  const { t } = useI18n()
  const raw = params.get('id') ?? ''
  const id = ID.test(raw) ? raw : null
  const query = useLichessGame(id)

  useEffect(() => {
    window.scrollTo(0, 0)
  }, [id])

  const missing = <StateNote title={t('game.missing.title')} text={t('game.missing.text')} className={card} />
  if (id === null) return <Shell>{missing}</Shell>
  if (query.isPending) return <Shell><LoadingNote what={t('what.game')} /></Shell>
  if (query.isError) {
    return (
      <Shell>
        {isClientError(query.error) ? missing : <ErrorNote what={t('what.game')} onRetry={() => void query.refetch()} />}
      </Shell>
    )
  }
  // Keyed by game: going to the next one starts again from its last position.
  return <Game key={query.data.lichess_id} game={query.data} />
}

function Shell({ children }: { children: ReactNode }) {
  return (
    <main className="grid content-start gap-6 px-4 pt-3 pb-10 sm:px-8 sm:pt-5">
      <div className="-mb-4">
        <BackLink fallback="partite" />
      </div>
      {children}
    </main>
  )
}

function Game({ game: g }: { game: LichessGameDetail }) {
  const i18n = useI18n()
  const { t, lang } = i18n
  const last = g.positions.length - 1
  const [current, setCurrent] = useState(last)
  const go = (position: number) => setCurrent(Math.max(0, Math.min(last, position)))

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return
      const target = event.target as HTMLElement | null
      if (target?.closest('input, select, textarea, [contenteditable="true"]')) return
      const next = { ArrowLeft: current - 1, ArrowRight: current + 1, Home: 0, End: last }[event.key]
      if (next === undefined) return
      event.preventDefault()
      setCurrent(Math.max(0, Math.min(last, next)))
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [current, last])

  const position = g.positions[current]
  const lastMove = current > 0 ? (g.moves[current - 1]?.uci ?? null) : null
  const them = g.color === 'white' ? 'black' : 'white'
  const commentary = pickText(lang, { it: g.commentary?.it, en: g.commentary?.en })
  const chances = g.analysed ? g.positions.map((p) => p.chances ?? 0) : null

  return (
    <Shell>
      <Head game={g} />
      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,520px)_minmax(0,1fr)] xl:gap-8">
        <section aria-label={t('game.board')} className="grid min-w-0 gap-2.5">
          <Player colour={them} label={g.opponent} detail={opponentDetail(i18n, g)} badge={g.opponent_title} />
          <Board fen={position?.fen ?? ''} lastMove={lastMove} orientation={g.color} />
          <Player colour={g.color} label={`darwin-chess-bot · gen-${g.generation_id}`} detail={t(`colour.${g.color}`)} />
          <Controls current={current} last={last} go={go} moves={g.moves} />
        </section>
        <div className="grid min-w-0 gap-6">
          <Panel title={t('game.chart')} help={t('game.chart.help')}>
            {chances ? (
              <>
                <EvalChart chances={chances} judgements={g.moves.map((m) => m.judgement)} current={current} onSelect={go} />
                <p className="mt-2 text-[13px] text-muted-foreground tabular-nums">
                  {current === 0 ? t('game.start') : t('game.after', { move: `${moveNumber(current - 1)} ${g.moves[current - 1]?.san ?? ''}` })}
                  {position?.eval_cp !== undefined && (
                    <> · {t('game.eval', { eval: pawns(i18n, position.eval_cp) })}</>
                  )}
                </p>
              </>
            ) : (
              <StateNote title={t('game.noAnalysis.title')} text={t('game.noAnalysis.text')} />
            )}
          </Panel>
          <Panel title={t('game.moves')}>
            <MoveList moves={g.moves} current={current} go={go} />
          </Panel>
          {g.sides && <Review game={g} sides={g.sides} go={go} />}
          {commentary && (
            <Panel title={t('game.commentary')}>
              <p lang={commentary.lang} className="max-w-[72ch] text-[14px] leading-relaxed text-pretty">{commentary.text}</p>
            </Panel>
          )}
        </div>
      </div>
      <GameNav game={g} />
    </Shell>
  )
}

function opponentDetail(i18n: I18n, g: LichessGameDetail): string {
  const { t } = i18n
  const colour = t(`colour.${g.color === 'white' ? 'black' : 'white'}`)
  return g.opponent_rating === null ? colour : `${colour} · ${g.opponent_rating}`
}

function Head({ game: g }: { game: LichessGameDetail }) {
  const { t, label, f } = useI18n()
  return (
    <header className="grid gap-1.5">
      <GameNav game={g} compact />
      <h1 className="text-[26px] font-semibold tracking-tight sm:text-[30px]">{t('lichess.heading', { opponent: g.opponent })}</h1>
      <p className="flex flex-wrap items-center gap-x-3.5 gap-y-1.5 text-[13px] text-muted-foreground tabular-nums">
        <b className={cn('font-semibold', RESULT_TONE[g.result ?? ''])}>{g.result ? label('result', g.result) : g.status}</b>
        <span>{t('lichess.as', { gen: g.generation_id, colour: t(`colour.${g.color}`) })}</span>
        <span>{t(`speed.${g.speed}`)} {g.time_control}</span>
        <span>{g.rated ? t('game.rated') : t('lichess.unrated')}</span>
        {g.finished_at && <span>{f.dateTime(g.finished_at)}</span>}
        {g.rating_after !== null && <span>{t('game.ratingAfter', { rating: g.rating_after })}</span>}
        <a href={g.url} target="_blank" rel="noreferrer"
           className="inline-flex cursor-pointer items-center gap-1.5 font-medium text-live underline-offset-4 hover:underline">
          {t('lichess.open')} <ExternalLink aria-hidden className="size-3.5" />
        </a>
      </p>
    </header>
  )
}

function Controls({ current, last, go, moves }: { current: number; last: number; go: (p: number) => void; moves: GameMove[] }) {
  const t = useI18n().t
  const button = (icon: ReactNode, labelKey: MessageKey, target: number, disabled: boolean) => (
    <button
      type="button"
      aria-label={t(labelKey)}
      disabled={disabled}
      onClick={() => go(target)}
      className="inline-flex size-9 cursor-pointer items-center justify-center rounded-full bg-card text-foreground shadow-[inset_0_0_0_1px_var(--border)] transition-colors hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring/60 focus-visible:outline-none disabled:cursor-default disabled:text-muted-foreground disabled:hover:bg-card"
    >
      {icon}
    </button>
  )
  const move = current > 0 ? moves[current - 1] : undefined
  return (
    <div className="grid gap-1.5">
      <div role="group" aria-label={t('game.controls')} className="flex items-center gap-1.5">
        {button(<ChevronFirst aria-hidden className="size-4" />, 'game.first', 0, current === 0)}
        {button(<ChevronLeft aria-hidden className="size-4" />, 'game.prev', current - 1, current === 0)}
        {button(<ChevronRight aria-hidden className="size-4" />, 'game.next', current + 1, current === last)}
        {button(<ChevronLast aria-hidden className="size-4" />, 'game.last', last, current === last)}
        <span aria-live="polite" className="ml-2 font-mono text-[13px] text-muted-foreground tabular-nums">
          {move ? `${moveNumber(current - 1)} ${move.san}` : t('game.start')}
          {move?.judgement && <b className={cn('ml-0.5', MARK_TONE[move.judgement])}>{MARK[move.judgement]}</b>}
        </span>
      </div>
      <p className="hidden text-[12px] text-muted-foreground sm:block">{t('game.keys')}</p>
    </div>
  )
}

/** The moves in pairs, each one a button that puts its position on the board. */
function MoveList({ moves, current, go }: { moves: GameMove[]; current: number; go: (p: number) => void }) {
  const { t, label } = useI18n()
  const box = useRef<HTMLOListElement>(null)
  useEffect(() => {
    // Scrolls the list only, never the page: scrollIntoView would move the window too.
    const list = box.current
    const cell = list?.querySelector<HTMLElement>('[aria-current="true"]')
    if (!list || !cell) return
    const top = cell.offsetTop - list.offsetTop
    if (top < list.scrollTop || top + cell.offsetHeight > list.scrollTop + list.clientHeight) {
      list.scrollTop = top - list.clientHeight / 2
    }
  }, [current])
  if (moves.length === 0) return <p className="text-[13px] text-muted-foreground">{t('arena.noMoves')}</p>
  const rows: [GameMove, GameMove | undefined][] = []
  for (let i = 0; i < moves.length; i += 2) rows.push([moves[i] as GameMove, moves[i + 1]])
  const cell = (move: GameMove | undefined, ply: number) =>
    move ? (
      <button
        type="button"
        aria-current={current === ply + 1 ? 'true' : undefined}
        aria-label={move.judgement ? `${move.san}, ${label('judgement', move.judgement)}` : move.san}
        onClick={() => go(ply + 1)}
        className={cn(
          'flex cursor-pointer items-baseline gap-0.5 rounded-md px-1.5 py-1 text-left transition-colors hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring/60 focus-visible:outline-none',
          current === ply + 1 && 'bg-live/22 font-medium hover:bg-live/22',
        )}
      >
        {move.san}
        {move.judgement && <b className={cn('font-semibold', MARK_TONE[move.judgement])}>{MARK[move.judgement]}</b>}
      </button>
    ) : (
      <span />
    )
  return (
    // Down the first column, then the next: on a phone one column that scrolls on its own.
    <ol ref={box} className="relative max-h-[360px] gap-x-6 overflow-y-auto font-mono text-[13px] tabular-nums sm:max-h-none sm:columns-2 sm:overflow-visible xl:columns-3">
      {rows.map(([white, black], i) => (
        <li key={i} className="grid h-[30px] break-inside-avoid grid-cols-[30px_1fr_1fr] items-center">
          <span className="text-[11px] text-muted-foreground">{i + 1}</span>
          {cell(white, 2 * i)}
          {cell(black, 2 * i + 1)}
        </li>
      ))}
    </ol>
  )
}

function Review({ game: g, sides, go }: { game: LichessGameDetail; sides: { us: SideReview; them: SideReview }; go: (p: number) => void }) {
  const i18n = useI18n()
  const { t } = i18n
  const turn = g.turning_point
  const move = turn === null ? undefined : g.moves[turn]
  const before = turn === null ? undefined : g.positions[turn]?.eval_cp
  const after = turn === null ? undefined : g.positions[turn + 1]?.eval_cp
  const rows: [string, SideReview][] = [['darwin-chess-bot', sides.us], [g.opponent, sides.them]]
  return (
    <Panel title={t('game.review')} help={t('game.acpl.help')}>
      <div className="grid gap-4">
        <div className="text-[14px]">
          <b className="block text-[12px] font-medium text-muted-foreground">{t('game.turning')}</b>
          {turn !== null && move ? (
            <p className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
              <span>
                <span className="font-mono font-medium">
                  {moveNumber(turn)} {move.san}
                  {move.judgement && <b className={MARK_TONE[move.judgement]}>{MARK[move.judgement]}</b>}
                </span>{' '}
                {t('game.turning.text', {
                  who: move.ours ? t('game.who.us') : t('game.who.them'),
                  before: before === undefined ? '' : pawns(i18n, before),
                  after: after === undefined ? '' : pawns(i18n, after),
                })}
              </span>
              <button type="button" onClick={() => go(turn + 1)}
                      className="cursor-pointer rounded-sm text-[13px] font-medium text-live underline-offset-4 hover:underline focus-visible:ring-2 focus-visible:ring-ring/60 focus-visible:outline-none">
                {t('game.turning.go')}
              </button>
            </p>
          ) : (
            <p className="text-muted-foreground">{t('game.turning.none')}</p>
          )}
        </div>
        <table className="w-full text-[13px] tabular-nums">
          <thead>
            <tr className="text-left text-[12px] text-muted-foreground">
              <th className="pb-1.5 font-medium"><span className="sr-only">{t('game.review.side')}</span></th>
              {JUDGEMENTS.map((j) => (
                <th key={j} className="pb-1.5 text-right font-medium">
                  <span className={cn('font-mono font-semibold', MARK_TONE[j])}>{MARK[j]}</span>{' '}
                  <span className="hidden sm:inline">{t(`game.review.${j}`)}</span>
                </th>
              ))}
              <th className="pb-1.5 text-right font-medium">
                {t('game.acpl')}
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map(([name, side]) => (
              <tr key={name} className="border-t">
                <th scope="row" className="py-1.5 pr-3 text-left font-semibold">
                  <span className="block max-w-[14ch] truncate sm:max-w-[28ch]">{name}</span>
                </th>
                {JUDGEMENTS.map((j) => (
                  <td key={j} className="py-1.5 text-right font-mono">{side[j]}</td>
                ))}
                <td className="py-1.5 text-right font-mono">{side.acpl ?? '-'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  )
}

/** The games on either side, oldest on the left; above the title, and again at the end. */
function GameNav({ game: g, compact }: { game: LichessGameDetail; compact?: boolean }) {
  const { t } = useI18n()
  const pill = 'inline-flex h-7 cursor-pointer items-center gap-1.5 rounded-full bg-muted px-3 text-[12px] font-medium text-muted-foreground transition-colors hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/60 focus-visible:outline-none'
  return (
    <nav aria-label={t('game.nav')} className={cn('flex flex-wrap justify-between gap-1.5', compact && 'mb-1')}>
      <span className="flex flex-wrap gap-1.5">
        {g.older && (
          <a href={href('partita', { id: g.older })} className={pill}>
            <ArrowLeft aria-hidden className="size-3.5" />{t('game.older')}
          </a>
        )}
        {compact && <a href={href('partite')} className={pill}>{t('game.all')}</a>}
      </span>
      {g.newer && (
        <a href={href('partita', { id: g.newer })} className={pill}>
          {t('game.newer')}<ArrowRight aria-hidden className="size-3.5" />
        </a>
      )}
    </nav>
  )
}
