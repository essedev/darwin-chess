/** "Newer" / "older" under a paged list: a quiet pill, greyed out at either end. */
export function PageButton({ disabled, onClick, children }: { disabled: boolean; onClick: () => void; children: string }) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className="h-8 cursor-pointer rounded-full bg-card px-3.5 text-[13px] font-medium text-foreground shadow-[inset_0_0_0_1px_var(--border)] transition-colors hover:bg-muted disabled:cursor-default disabled:opacity-40 disabled:hover:bg-card"
    >
      {children}
    </button>
  )
}
