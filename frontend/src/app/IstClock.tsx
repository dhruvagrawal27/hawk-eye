import { useEffect, useState } from 'react'
import { Clock } from 'lucide-react'
import { formatISTTime } from '@/lib/format'

/** Live IST clock — a quiet reminder that all times display in IST (CONTEXT.md §6). */
export function IstClock() {
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(id)
  }, [])
  return (
    <span className="hidden items-center gap-1.5 text-xs tabular-nums text-muted-foreground lg:inline-flex">
      <Clock className="size-3.5" />
      {formatISTTime(now)} IST
    </span>
  )
}
