import { ErrorNote, LoadingNote, StateNote, card } from '@/components/page'
import { dateTime, num, plainText, signed } from '@/features/live/format'
import { type GenerationDetail, useGenerationsDetail } from '@/lib/api'
import { href } from '@/lib/use-route'
import { cn } from '@/lib/utils'

export function GenerationTimeline() {
  const generations = useGenerationsDetail()
  return (
    <section aria-labelledby="generations" className="grid min-w-0 gap-4">
      <h2 id="generations" className="text-[19px] font-semibold tracking-tight">Le generazioni</h2>
      {generations.isPending ? (
        <LoadingNote what="le generazioni" />
      ) : generations.isError ? (
        <ErrorNote what="le generazioni" onRetry={() => void generations.refetch()} />
      ) : generations.data.length === 0 ? (
        <StateNote title="Nessuna generazione ancora" text="Il laboratorio non è ancora partito." className={card} />
      ) : (
        <ol className="grid">
          {generations.data.map((g, i) => (
            <GenerationItem key={g.id} generation={g} champion={i === 0} last={i === generations.data.length - 1} />
          ))}
        </ol>
      )}
    </section>
  )
}

function GenerationItem({ generation: g, champion, last }: { generation: GenerationDetail; champion: boolean; last: boolean }) {
  const seed = g.id === 0
  const headline = seed
    ? 'Il seme: un progetto Rust vuoto, da cui parte tutto'
    : g.hypothesis
      ? plainText(g.hypothesis)
      : 'Nessuna ipotesi registrata'
  return (
    <li className="relative grid grid-cols-[20px_minmax(0,1fr)] gap-x-3">
      <span aria-hidden className="relative flex justify-center">
        {!last && <i className="absolute top-3 bottom-0 w-px bg-border" />}
        <i className={cn('relative mt-[7px] size-2.5 rounded-full ring-4 ring-background', champion ? 'bg-live' : 'bg-muted-foreground/50')} />
      </span>
      <article className="grid min-w-0 gap-2 pb-7">
        <p className="flex flex-wrap items-baseline gap-x-2.5 gap-y-0.5 text-[12px] text-muted-foreground">
          <span className={cn('font-mono text-[13px] font-medium', champion ? 'text-live' : 'text-foreground')}>gen-{g.id}</span>
          {champion && <span className="font-medium text-live">campione attuale</span>}
          <time dateTime={g.created_at}>{dateTime(g.created_at)}</time>
        </p>
        <h3 className="text-[16px] leading-snug font-semibold text-pretty">{headline}</h3>
        {!seed && <Facts generation={g} />}
        {g.lesson && (
          <p className="text-[13px] leading-relaxed text-muted-foreground">
            <span className="font-medium text-foreground">Cosa ha imparato: </span>
            {plainText(g.lesson)}
          </p>
        )}
        <a
          href={seed ? href('codice', { ref: 'gen-0' }) : href('codice', { diff: `gen-${g.id}` })}
          className="w-fit cursor-pointer text-[13px] font-medium text-live underline-offset-4 hover:underline"
        >
          {seed ? 'Sfoglia il codice di partenza' : 'Cosa è cambiato nel codice'}
        </a>
      </article>
    </li>
  )
}

function Facts({ generation: g }: { generation: GenerationDetail }) {
  const facts: { text: string; tone?: string }[] = []
  if (g.id === 1) facts.push({ text: 'batte il giocatore casuale', tone: 'text-good' })
  else if (g.elo_vs_parent !== null) facts.push({ text: `${signed(g.elo_vs_parent)} Elo sul campione precedente`, tone: 'text-good' })
  if (g.below_ladder) facts.push({ text: 'sotto la scala di Stockfish' })
  else if (g.elo_absolute !== null) facts.push({ text: `circa ${num(Math.round(g.elo_absolute))} Elo` })
  facts.push({ text: g.tried <= 1 ? 'al primo tentativo' : `dopo ${g.tried} tentativi` })
  if (g.diff_stat) {
    const { files, insertions, deletions } = g.diff_stat
    facts.push({ text: `${files === 1 ? '1 file' : `${files} file`} · +${num(insertions)} −${num(deletions)} righe` })
  }
  const l = g.lichess
  return (
    <div className="grid gap-1.5">
      <p className="flex flex-wrap gap-x-3 gap-y-1 text-[13px]">
        {facts.map((f) => (
          <span key={f.text} className={cn('font-medium', f.tone ?? 'text-muted-foreground')}>{f.text}</span>
        ))}
      </p>
      {l && l.games > 0 && (
        <p className="text-[13px] text-muted-foreground">
          Su Lichess: <span className="font-mono font-medium text-foreground tabular-nums">{num(l.performance)}</span> di
          performance in {l.games === 1 ? '1 partita' : `${l.games} partite`} ({l.wins} vinte, {l.draws} patte, {l.losses} perse)
        </p>
      )}
    </div>
  )
}
