import { useMutation } from '@tanstack/react-query'
import { Download, FileSpreadsheet, FileText, Loader2, RefreshCw } from 'lucide-react'
import { apiClient } from '@/lib/apiClient'
import { ApiError } from '@/lib/http'
import { formatINR, formatIST, formatISTDate, isTokenizedPii } from '@/lib/format'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { EmptyState } from '@/components/ui/empty-state'
import { MaskedPII } from '@/components/MaskedPII'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { toast } from '@/components/ui/toaster'
import type { ReportExport, ReportLineItem, ReportType } from '@/lib/types'

/** Trigger a client-side download of the report's mock payload (Blob + transient anchor). */
function downloadReport(report: ReportExport): void {
  const content = report.download_content
  if (!content) {
    toast.error('Nothing to download', { description: 'This report has no generated content yet.' })
    return
  }
  const filename = report.download_filename ?? `${report.type}-report-${report.report_id}.csv`
  const blob = new Blob([content], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
  toast.success('Download started', { description: filename })
}

function totalExposure(items: ReportLineItem[]): number {
  return items.reduce((sum, i) => sum + (i.amount_inr ?? 0), 0)
}

function LineItemsTable({ items }: { items: ReportLineItem[] }) {
  if (items.length === 0) {
    return (
      <p className="px-1 py-3 text-xs text-muted-foreground">
        No line items in this report period.
      </p>
    )
  }
  return (
    <Table>
      <TableHeader>
        <TableRow className="hover:bg-transparent">
          <TableHead className="w-28">Ref</TableHead>
          <TableHead>Entity</TableHead>
          <TableHead>Category</TableHead>
          <TableHead>Detail</TableHead>
          <TableHead className="text-right">Amount</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {items.map((item) => (
          <TableRow key={item.ref}>
            <TableCell className="font-mono text-xs">{item.ref}</TableCell>
            <TableCell>
              {item.entity_id ? (
                isTokenizedPii(item.entity_id) ? (
                  <MaskedPII
                    value={item.entity_id}
                    entityId={item.entity_id}
                    alertId={item.alert_id ?? undefined}
                  />
                ) : (
                  <span className="font-mono text-xs">{item.entity_id}</span>
                )
              ) : (
                <span className="text-xs text-muted-foreground">—</span>
              )}
            </TableCell>
            <TableCell>
              {item.category ? (
                <Badge variant="outline" className="font-normal">
                  {item.category}
                </Badge>
              ) : (
                <span className="text-xs text-muted-foreground">—</span>
              )}
            </TableCell>
            <TableCell className="max-w-[22rem] text-xs text-muted-foreground">
              <span className="line-clamp-2">{item.detail ?? '—'}</span>
            </TableCell>
            <TableCell className="text-right font-mono font-medium tabular-nums">
              {item.amount_inr != null ? formatINR(item.amount_inr) : '—'}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}

function ReportPreview({ report }: { report: ReportExport }) {
  const total = totalExposure(report.line_items)
  return (
    <div className="space-y-3 rounded-md border border-border bg-muted/20 p-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="flex items-center gap-2 text-sm font-medium">
            {report.type.toUpperCase()} draft
            <Badge variant={report.status === 'ready' ? 'success' : 'warning'}>
              {report.status === 'ready' ? 'Ready' : 'Generating'}
            </Badge>
          </p>
          <p className="mt-0.5 font-mono text-[0.7rem] text-muted-foreground">{report.report_id}</p>
        </div>
        <Button
          type="button"
          size="sm"
          disabled={report.status !== 'ready' || !report.download_content}
          onClick={() => downloadReport(report)}
        >
          <Download className="size-3.5" />
          Download {report.download_filename ? `(${report.download_filename})` : 'CSV'}
        </Button>
      </div>

      <p className="text-xs text-muted-foreground">{report.summary}</p>

      <div className="flex flex-wrap gap-x-6 gap-y-1 text-[0.7rem] text-muted-foreground">
        {report.period ? (
          <span>
            Period{' '}
            <span className="font-mono tabular-nums">
              {formatISTDate(report.period.from)} – {formatISTDate(report.period.to)}
            </span>
          </span>
        ) : null}
        <span>
          Generated <span className="font-mono tabular-nums">{formatIST(report.generated_ts)}</span>
        </span>
        <span className="tabular-nums">
          {report.line_items.length} line item{report.line_items.length === 1 ? '' : 's'}
        </span>
        <span>
          Total exposure{' '}
          <span className="font-mono font-medium tabular-nums text-foreground">
            {formatINR(total)}
          </span>
        </span>
      </div>

      <Separator />
      <div className="overflow-hidden rounded-md border border-border">
        <LineItemsTable items={report.line_items} />
      </div>
    </div>
  )
}

interface ExportCardConfig {
  type: ReportType
  title: string
  icon: typeof FileText
  description: string
  context: string
  fetcher: () => Promise<ReportExport>
}

function ExportCard({ config }: { config: ExportCardConfig }) {
  const Icon = config.icon
  const generate = useMutation({
    mutationFn: config.fetcher,
    onError: (err) =>
      toast.error('Report generation failed', {
        description: err instanceof ApiError ? err.message : 'Unexpected error. Please retry.',
      }),
  })

  const report = generate.data

  return (
    <Card>
      <CardHeader className="gap-2 pb-3">
        <CardTitle className="flex items-center gap-2">
          <Icon className="size-4 text-primary" />
          {config.title}
        </CardTitle>
        <CardDescription>{config.description}</CardDescription>
        <p className="rounded-md bg-muted/40 px-2.5 py-1.5 text-[0.7rem] text-muted-foreground">
          {config.context}
        </p>
      </CardHeader>
      <CardContent className="space-y-3">
        <Button
          type="button"
          variant={report ? 'outline' : 'default'}
          disabled={generate.isPending}
          onClick={() => generate.mutate()}
        >
          {generate.isPending ? (
            <Loader2 className="size-4 animate-spin" />
          ) : report ? (
            <RefreshCw className="size-4" />
          ) : (
            <Icon className="size-4" />
          )}
          {report
            ? `Regenerate ${config.type.toUpperCase()} draft`
            : `Generate ${config.type.toUpperCase()} draft`}
        </Button>

        {generate.isPending ? (
          <p className="text-xs text-muted-foreground">Compiling report from confirmed alerts…</p>
        ) : report ? (
          <ReportPreview report={report} />
        ) : generate.isError ? null : (
          <EmptyState
            icon={Icon}
            title={`No ${config.type.toUpperCase()} draft yet`}
            description="Generate a draft to preview the summary, line items, and download the file."
          />
        )}
      </CardContent>
    </Card>
  )
}

const EXPORTS: ExportCardConfig[] = [
  {
    type: 'crilc',
    title: 'CRILC export',
    icon: FileSpreadsheet,
    description:
      'Central Repository of Information on Large Credits — large-exposure regulatory filing.',
    context:
      'CRILC reporting threshold: aggregate exposure ≥ ₹3 crore held ≥ 7 days, assessed within the 180-day rolling window.',
    fetcher: () => apiClient.getCrilcReport(),
  },
  {
    type: 'fmr',
    title: 'FMR export',
    icon: FileText,
    description:
      'Fraud Monitoring Return — RBI fraud reporting draft for MLRO review and sign-off.',
    context:
      'FMR draft is prepared for the MLRO. It compiles confirmed-fraud alerts; the MLRO reviews and authorises the regulatory submission.',
    fetcher: () => apiClient.getFmrReport(),
  },
]

/**
 * One-click regulatory exports (FRONTEND-12; blueprint Part 11 reporting + Part 24.4). CRILC and FMR
 * drafts are fetched on demand via `apiClient.getCrilcReport()` / `apiClient.getFmrReport()`, previewed
 * (summary + line-items table), and downloaded client-side as `download_content` → `download_filename`
 * (Blob + anchor). These are *drafts for review*, never an automatic filing.
 */
export function RegulatoryExport() {
  return (
    <div className="space-y-3">
      <Card className="border-dashed bg-muted/10">
        <CardContent className="flex items-start gap-2 p-3 text-xs text-muted-foreground">
          <FileText className="mt-0.5 size-4 shrink-0 text-primary" />
          <span>
            These exports generate{' '}
            <span className="font-medium text-foreground">drafts for human review</span> — they do
            not file with the regulator. PII stays tokenized in the preview; unmasking is a
            separate, audited action.
          </span>
        </CardContent>
      </Card>
      <div className="grid gap-3 lg:grid-cols-2">
        {EXPORTS.map((config) => (
          <ExportCard key={config.type} config={config} />
        ))}
      </div>
    </div>
  )
}
