/**
 * Sandboxed Grafana embed (FRONTEND-13; blueprint Part 24.4 screen 8 — Admin / system health).
 *
 * Renders an operations dashboard inside a **sandboxed** iframe sourced from `env.grafanaUrl + path`.
 * The sandbox keeps the embedded dashboard from scripting the console or navigating the top frame;
 * Grafana itself only carries de-identified ops telemetry (no case PII). A header shows the resolved
 * URL and offers an "open in Grafana" escape hatch.
 */
import { useEffect, useState } from 'react'
import { ExternalLink, Gauge, PlugZap, RefreshCw } from 'lucide-react'
import { env } from '@/lib/env'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

function joinUrl(base: string, path: string): string {
  const trimmedBase = base.replace(/\/+$/, '')
  const trimmedPath = path.replace(/^\/+/, '')
  return trimmedPath ? `${trimmedBase}/${trimmedPath}` : trimmedBase
}

type Reach = 'checking' | 'up' | 'down'

/**
 * Probe whether the Grafana origin is reachable before we commit to an <iframe>.
 * A bare iframe to a down server renders the browser's raw "refused to connect"
 * chrome, which looks broken. We do a no-cors fetch (we only care that the socket
 * answers, not the body) with a short timeout; on any network error -> 'down', so
 * we can show a tidy placeholder instead. Re-runs when `nonce` (reload) changes.
 */
function useReachable(url: string, nonce: number): Reach {
  const [state, setState] = useState<Reach>('checking')
  useEffect(() => {
    let cancelled = false
    setState('checking')
    if (typeof fetch !== 'function') {
      setState('up') // SSR/test env without fetch — fall back to optimistic render
      return
    }
    const ctrl = new AbortController()
    const timer = setTimeout(() => ctrl.abort(), 3500)
    fetch(url, { mode: 'no-cors', signal: ctrl.signal })
      .then(() => !cancelled && setState('up'))
      .catch(() => !cancelled && setState('down'))
      .finally(() => clearTimeout(timer))
    return () => {
      cancelled = true
      clearTimeout(timer)
      ctrl.abort()
    }
  }, [url, nonce])
  return state
}

export function GrafanaEmbed({
  // Pin a recent window + auto-refresh so the embed always shows live data — without `from/to`
  // Grafana can fall back to a persisted range (e.g. "Previous year") and render "No data".
  path = '/d/hawk-eye-ops?kiosk&from=now-30m&to=now&refresh=10s',
  title = 'System health (Grafana)',
}: {
  path?: string
  title?: string
}) {
  const [nonce, setNonce] = useState(0)
  const src = joinUrl(env.grafanaUrl, path)
  const reach = useReachable(env.grafanaUrl, nonce)

  return (
    <Card className="overflow-hidden">
      <CardHeader className="flex flex-row items-center justify-between gap-2 space-y-0 pb-3">
        <div className="flex items-center gap-2">
          <Gauge className="size-4 text-primary" />
          <CardTitle>{title}</CardTitle>
        </div>
        <div className="flex items-center gap-1.5">
          <code className="hidden max-w-[18rem] truncate rounded bg-muted px-2 py-1 text-[0.7rem] text-muted-foreground sm:block">
            {src}
          </code>
          <Button
            variant="ghost"
            size="icon"
            className="size-8"
            aria-label="Reload dashboard"
            onClick={() => setNonce((n) => n + 1)}
          >
            <RefreshCw className="size-4" />
          </Button>
          <Button variant="outline" size="sm" asChild>
            <a href={src} target="_blank" rel="noreferrer noopener">
              <ExternalLink className="size-3.5" />
              Open
            </a>
          </Button>
        </div>
      </CardHeader>
      <CardContent className="p-0">
        {reach === 'up' ? (
          <iframe
            key={nonce}
            title={title}
            src={src}
            loading="lazy"
            className="h-[26rem] w-full border-0 bg-background"
            referrerPolicy="no-referrer"
            sandbox="allow-scripts allow-same-origin allow-popups"
          />
        ) : (
          <div className="flex h-[26rem] w-full flex-col items-center justify-center gap-3 bg-muted/30 px-6 text-center">
            <PlugZap className="size-8 text-muted-foreground" />
            {reach === 'checking' ? (
              <p className="text-sm text-muted-foreground">Connecting to Grafana…</p>
            ) : (
              <>
                <p className="text-sm font-medium">Operations dashboard isn’t running here</p>
                <p className="max-w-md text-xs text-muted-foreground">
                  Grafana (ops metrics) isn’t part of the pilot stack, so there’s nothing to
                  embed yet. The rest of Hawk-Eye — alerts, narratives, cases, audit — works
                  without it. Start the full monitoring stack to enable this panel, then reload.
                </p>
                <div className="flex items-center gap-2 pt-1">
                  <Button variant="outline" size="sm" onClick={() => setNonce((n) => n + 1)}>
                    <RefreshCw className="size-3.5" />
                    Retry
                  </Button>
                  <Button variant="ghost" size="sm" asChild>
                    <a href={src} target="_blank" rel="noreferrer noopener">
                      <ExternalLink className="size-3.5" />
                      Open if running elsewhere
                    </a>
                  </Button>
                </div>
              </>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
