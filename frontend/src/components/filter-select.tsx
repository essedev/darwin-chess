import { Select } from '@base-ui/react/select'
import { Check, ChevronDown } from 'lucide-react'
import { cn } from '@/lib/utils'

export type FilterOption = { value: string; label: string; count?: string }

/**
 * A filter that picks one value from a short list, drawn like the other filters (muted pill,
 * same height) instead of the browser's own select; the menu opens under it.
 */
export function FilterSelect(props: {
  label: string
  value: string
  options: FilterOption[]
  onChange: (value: string) => void
  className?: string
}) {
  const items = props.options.map((o) => ({ value: o.value, label: o.label }))
  return (
    <Select.Root
      value={props.value}
      items={items}
      onValueChange={(value) => {
        if (typeof value === 'string') props.onChange(value)
      }}
    >
      <Select.Trigger
        aria-label={props.label}
        className={cn(
          'inline-flex h-[34px] cursor-pointer items-center gap-2 rounded-[14px] bg-muted pr-2.5 pl-3 text-[13px] font-medium text-foreground transition-colors',
          'hover:bg-muted/70 focus-visible:ring-2 focus-visible:ring-ring/60 focus-visible:outline-none data-[popup-open]:bg-muted/70',
          props.className,
        )}
      >
        <Select.Value className="truncate" />
        <Select.Icon className="flex text-muted-foreground">
          <ChevronDown aria-hidden className="size-3.5" />
        </Select.Icon>
      </Select.Trigger>
      <Select.Portal>
        <Select.Positioner sideOffset={6} align="start" alignItemWithTrigger={false} className="z-40 outline-none">
          <Select.Popup
            className={cn(
              'max-h-[min(360px,var(--available-height))] min-w-[var(--anchor-width)] overflow-y-auto rounded-[12px] border bg-popover p-1 text-popover-foreground shadow-[0_8px_24px_rgb(0_0_0/0.14)] outline-none',
              'origin-[var(--transform-origin)] transition-[opacity,transform] duration-100 data-[ending-style]:scale-95 data-[ending-style]:opacity-0 data-[starting-style]:scale-95 data-[starting-style]:opacity-0',
            )}
          >
            <Select.List>
              {props.options.map((option) => (
                <Select.Item
                  key={option.value}
                  value={option.value}
                  className="grid h-8 cursor-pointer grid-cols-[16px_1fr_auto] items-center gap-2 rounded-[8px] pr-2.5 pl-2 text-[13px] outline-none select-none data-[highlighted]:bg-muted data-[selected]:font-medium"
                >
                  <Select.ItemIndicator className="flex text-foreground">
                    <Check aria-hidden className="size-3.5" />
                  </Select.ItemIndicator>
                  <Select.ItemText className="col-start-2 whitespace-nowrap">{option.label}</Select.ItemText>
                  {option.count !== undefined && (
                    <span className="font-mono text-[11px] text-muted-foreground tabular-nums">{option.count}</span>
                  )}
                </Select.Item>
              ))}
            </Select.List>
          </Select.Popup>
        </Select.Positioner>
      </Select.Portal>
    </Select.Root>
  )
}
