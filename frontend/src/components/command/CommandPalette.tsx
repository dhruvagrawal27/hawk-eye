/**
 * ⌘K command palette (study: terminal-grade command surface). A `cmdk` menu rendered inside our Radix
 * Dialog so it inherits the app's overlay/focus-trap/escape behaviour. Opens on ⌘/Ctrl-K, lists
 * `useCommands()` grouped (Navigation / Actions), fuzzy-filters as you type, and runs
 * `perform(navigate)` on Enter — then closes.
 *
 * Self-contained: it owns its open state and binds the hotkey itself, so wiring into the shell is a
 * single `<CommandPalette />`. `useCommandPalette()` is exported for callers that want to drive it from
 * a button (e.g. a "⌘K" affordance in the header).
 */
import * as React from 'react'
import { useNavigate } from 'react-router-dom'
import { Command as Cmdk } from 'cmdk'
import { Search, CornerDownLeft, type LucideIcon } from 'lucide-react'
import { Dialog, DialogContent } from '@/components/ui/dialog'
import { Eyebrow } from '@/components/ui/eyebrow'
import { useGlobalHotkeys } from '@/hooks/useHotkeys'
import { useCommands, type Command, type CommandGroup } from '@/lib/commands'
import { cn } from '@/lib/cn'

/** Open-state controller. Internal by default; exported so a header button can also toggle it. */
export function useCommandPalette(): {
  open: boolean
  setOpen: (open: boolean) => void
  toggle: () => void
} {
  const [open, setOpen] = React.useState(false)
  const toggle = React.useCallback(() => setOpen((o) => !o), [])
  return { open, setOpen, toggle }
}

/** Stable group order for rendering. */
const GROUP_ORDER: CommandGroup[] = ['Navigation', 'Actions']

function groupCommands(commands: Command[]): Array<{ group: CommandGroup; items: Command[] }> {
  return GROUP_ORDER.map((group) => ({
    group,
    items: commands.filter((c) => c.group === group),
  })).filter((g) => g.items.length > 0)
}

export function CommandPalette(): React.ReactElement {
  const { open, setOpen, toggle } = useCommandPalette()
  const navigate = useNavigate()
  const commands = useCommands()
  const grouped = React.useMemo(() => groupCommands(commands), [commands])

  // Bind ⌘/Ctrl-K to toggle the palette.
  useGlobalHotkeys({ onPalette: toggle })

  const run = React.useCallback(
    (command: Command) => {
      setOpen(false)
      // Close first (so a focus-stealing action like "focus triage search" lands after the dialog
      // releases the focus trap), then perform on the next tick.
      requestAnimationFrame(() => command.perform(navigate))
    },
    [navigate, setOpen],
  )

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent
        // Override the default dialog padding/width: the palette is a flush, full-bleed list.
        className="max-w-xl gap-0 overflow-hidden p-0"
        aria-label="Command palette"
      >
        <Cmdk
          label="Command palette"
          className="flex flex-col [&_[cmdk-group-heading]]:px-3 [&_[cmdk-group-heading]]:py-1.5"
        >
          <div className="flex items-center gap-2 border-b border-border px-3">
            <Search className="size-4 shrink-0 text-muted-foreground" aria-hidden />
            <Cmdk.Input
              autoFocus
              placeholder="Type a command or search…"
              className={cn(
                'h-11 w-full bg-transparent text-sm outline-none',
                'placeholder:text-muted-foreground',
              )}
            />
            {/* Leave room for DialogContent's built-in close (X) button sitting at top-right. */}
            <span className="w-5 shrink-0" aria-hidden />
          </div>

          <Cmdk.List className="max-h-[min(22rem,60vh)] overflow-y-auto overflow-x-hidden p-1.5">
            <Cmdk.Empty className="py-6 text-center font-mono text-2xs uppercase tracking-widest text-muted-foreground">
              No matching commands
            </Cmdk.Empty>

            {grouped.map(({ group, items }) => (
              <Cmdk.Group
                key={group}
                heading={<Eyebrow>{group}</Eyebrow>}
                className="pb-1"
              >
                {items.map((command) => (
                  <CommandRow key={command.id} command={command} onRun={run} />
                ))}
              </Cmdk.Group>
            ))}
          </Cmdk.List>
        </Cmdk>
      </DialogContent>
    </Dialog>
  )
}

interface CommandRowProps {
  command: Command
  onRun: (command: Command) => void
}

function CommandRow({ command, onRun }: CommandRowProps): React.ReactElement {
  const Icon: LucideIcon | undefined = command.icon
  return (
    <Cmdk.Item
      value={command.id}
      keywords={command.keywords}
      onSelect={() => onRun(command)}
      className={cn(
        'group flex cursor-pointer items-center gap-2.5 rounded-md px-2.5 py-2 text-sm text-foreground',
        'data-[selected=true]:bg-accent data-[selected=true]:text-accent-foreground',
        'aria-disabled:pointer-events-none aria-disabled:opacity-50',
      )}
    >
      {Icon ? (
        <Icon className="size-4 shrink-0 text-muted-foreground" aria-hidden />
      ) : (
        <span className="size-4 shrink-0" aria-hidden />
      )}
      <span className="flex-1 truncate">{command.title}</span>
      <CornerDownLeft
        className="size-3.5 shrink-0 text-muted-foreground opacity-0 transition-opacity group-data-[selected=true]:opacity-100"
        aria-hidden
      />
    </Cmdk.Item>
  )
}
