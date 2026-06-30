/**
 * Sandboxed Grafana embed (FRONTEND-13; blueprint Part 24.4 screen 8 — Admin / system health).
 *
 * Renders an operations dashboard inside a **sandboxed** iframe sourced from `env.grafanaUrl + path`.
 * The sandbox keeps the embedded dashboard from scripting the console or navigating the top frame;
 * Grafana itself only carries de-identified ops telemetry (no case PII). A header shows the resolved
 * URL and offers an "open in Grafana" escape hatch.
 */
import { useState } from 'react'
import { ExternalLink, Gauge, RefreshCw } from 'lucide-react'
import { env } from '@/lib/env'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

function joinUrl(base: string, path: string): string {
  const trimmedBase = base.replace(/\/+$/, '')
  const trimmedPath = path.replace(/^\/+/, '')
  return trimmedPath ? `${trimmedBase}/${trimmedPath}` : trimmedBase
}

export function GrafanaEmbed({
  path = '/d/hawk-eye-ops?kiosk',
  title = 'System health (Grafana)',
}: {
  path?: string
  title?: string
}) {
  const [nonce, setNonce] = useState(0)
  const src = joinUrl(env.grafanaUrl, path)

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
        <iframe
          key={nonce}
          title={title}
          src={src}
          loading="lazy"
          className="h-[26rem] w-full border-0 bg-background"
          referrerPolicy="no-referrer"
          sandbox="allow-scripts allow-same-origin allow-popups"
        />
      </CardContent>
    </Card>
  )
}
