import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Loader2, MessageSquarePlus, MessagesSquare } from 'lucide-react'
import { apiClient } from '@/lib/apiClient'
import { queryKeys } from '@/lib/queryKeys'
import { ApiError } from '@/lib/http'
import { formatIST, formatRelative, humanize } from '@/lib/format'
import { useAuth } from '@/auth/rbac'
import { ROLE_META } from '@/auth/capabilities'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Separator } from '@/components/ui/separator'
import { EmptyState } from '@/components/ui/empty-state'
import { InfoTip } from '@/components/ui/tooltip'
import { toast } from '@/components/ui/toaster'
import type { CaseNote } from '@/lib/types'

/** Initials for an actor token / username, capped at two glyphs. */
function initials(name: string): string {
  const cleaned = name.replace(/[_-]+/g, ' ').trim()
  const parts = cleaned.split(/\s+/).filter(Boolean)
  if (parts.length === 0) return '??'
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
}

/**
 * Threaded case notes (FRONTEND-5; blueprint Part 24.4 screen 4). Renders the running note thread and,
 * for roles holding `triage`, an inline composer that POSTs via `apiClient.addCaseNote` and invalidates
 * `queryKeys.case(id)`. Read-only roles see the thread without the composer.
 */
export function CaseNotes({ caseId, notes }: { caseId: string; notes: CaseNote[] }) {
  const { can, user } = useAuth()
  const queryClient = useQueryClient()
  const canAdd = can('triage')
  const [draft, setDraft] = useState('')

  const addNote = useMutation({
    mutationFn: (body: string) => apiClient.addCaseNote(caseId, { body }),
    onSuccess: () => {
      setDraft('')
      void queryClient.invalidateQueries({ queryKey: queryKeys.case(caseId) })
      toast.success('Note added to case')
    },
    onError: (err) =>
      toast.error('Could not add note', {
        description: err instanceof ApiError ? err.message : undefined,
      }),
  })

  const ordered = [...notes].sort((a, b) => +new Date(b.ts) - +new Date(a.ts))
  const trimmed = draft.trim()

  function submit() {
    if (!trimmed || addNote.isPending) return
    addNote.mutate(trimmed)
  }

  return (
    <div className="flex flex-col gap-3">
      {canAdd ? (
        <div className="space-y-2 rounded-lg border border-border bg-muted/20 p-3">
          <Textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
                e.preventDefault()
                submit()
              }
            }}
            placeholder="Add an investigation note… (⌘/Ctrl + Enter to post)"
            className="min-h-[68px] resize-y bg-background"
            disabled={addNote.isPending}
            aria-label="New case note"
          />
          <div className="flex items-center justify-between">
            <span className="text-[0.7rem] text-muted-foreground">
              Posted as{' '}
              <span className="font-medium text-foreground">
                {user?.name ?? user?.username ?? 'you'}
              </span>{' '}
              · notes are auditable
            </span>
            <Button size="sm" onClick={submit} disabled={!trimmed || addNote.isPending}>
              {addNote.isPending ? <Loader2 className="animate-spin" /> : <MessageSquarePlus />}
              Add note
            </Button>
          </div>
        </div>
      ) : null}

      {ordered.length === 0 ? (
        <EmptyState
          icon={MessagesSquare}
          title="No notes yet"
          description={
            canAdd
              ? 'Document what you checked and why. Notes are part of the case audit trail.'
              : 'Investigators have not added any notes to this case.'
          }
        />
      ) : (
        <ol className="space-y-2.5">
          {ordered.map((note, i) => (
            <li key={note.id} className="flex gap-2.5">
              <div className="flex flex-col items-center">
                <Avatar className="size-7">
                  <AvatarFallback className="text-[0.65rem]">
                    {initials(note.author)}
                  </AvatarFallback>
                </Avatar>
                {i < ordered.length - 1 ? (
                  <span className="mt-1 w-px flex-1 bg-border" aria-hidden />
                ) : null}
              </div>
              <div className="min-w-0 flex-1 rounded-lg border border-border bg-card px-3 py-2">
                <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
                  <span className="text-sm font-medium">{note.author}</span>
                  {note.author_role ? (
                    <span className="text-[0.7rem] text-muted-foreground">
                      {ROLE_META[note.author_role]?.short ?? humanize(note.author_role)}
                    </span>
                  ) : null}
                  <Separator orientation="vertical" className="h-3" />
                  <InfoTip label={formatIST(note.ts)}>
                    <span className="text-[0.7rem] tabular-nums text-muted-foreground">
                      {formatRelative(note.ts)}
                    </span>
                  </InfoTip>
                </div>
                <p className="mt-1 whitespace-pre-wrap break-words text-sm text-foreground/90">
                  {note.body}
                </p>
              </div>
            </li>
          ))}
        </ol>
      )}
    </div>
  )
}
