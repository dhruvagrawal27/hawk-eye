import { useState } from 'react'
import { FileDown, Loader2 } from 'lucide-react'
import { apiClient } from '@/lib/apiClient'
import { Button } from '@/components/ui/button'
import { toast } from '@/components/ui/toaster'
import { cn } from '@/lib/cn'
import type { Alert, ExplanationResponse, ReasonCode } from '@/lib/types'
import { formatINR, formatIST, formatPercent, formatSigned, statusLabel } from '@/lib/format'

/**
 * "Download PDF" for an alert's explainability report (self-contained). Opens a print-ready, formatted
 * report in a new window and triggers the browser's Save-as-PDF — no PDF dependency. Alert-only: it
 * explains, it never offers an action.
 */
const esc = (v: unknown) =>
  String(v ?? '').replace(
    /[&<>"]/g,
    (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]!,
  )

function reasonRow(r: ReasonCode): string {
  if (r.source === 'rule')
    return `<tr><td class="src">rule</td><td><b>${esc(r.code)}</b> — ${esc(r.detail)}</td></tr>`
  if (r.source === 'shap')
    return `<tr><td class="src">shap</td><td><b>${esc(r.feature)}</b> (${formatSigned(r.contribution)})</td></tr>`
  return `<tr><td class="src">graph</td><td>${esc(r.detail)}${r.ring_id ? ` · ${esc(r.ring_id)}` : ''}</td></tr>`
}

function buildReportHtml(alert: Alert, ex: ExplanationResponse | null): string {
  const shap = [...(ex?.shap ?? [])]
    .sort((a, b) => Math.abs(b.contribution) - Math.abs(a.contribution))
    .slice(0, 10)
  const rules = ex?.rules ?? []
  const reasons = alert.reason_codes ?? []
  const sevColor =
    { critical: '#b31d1d', high: '#c2410c', medium: '#b7791f', low: '#3f6f57' }[alert.severity] ??
    '#3f6f57'
  return `<!doctype html><html><head><meta charset="utf-8"><title>Hawk-Eye Explainability ${esc(alert.alert_id)}</title>
<style>
  @page{size:A4;margin:14mm 13mm}
  *{box-sizing:border-box}
  body{font-family:'Inter Variable',Inter,system-ui,sans-serif;color:#1c1a17;font-size:11px;line-height:1.5;margin:0}
  .mono{font-family:'JetBrains Mono Variable','JetBrains Mono',ui-monospace,monospace;font-variant-numeric:tabular-nums}
  .head{display:flex;justify-content:space-between;align-items:flex-start;border-bottom:2px solid #12564f;padding-bottom:8px}
  .mark{font-family:ui-monospace,monospace;font-weight:700;letter-spacing:.14em;color:#fff;background:#12564f;padding:4px 7px;border-radius:3px;font-size:10px}
  h1{font-size:16px;margin:0 0 0 0}
  .sub{color:#57514a;font-size:10px}
  .meta{text-align:right;color:#57514a;font-size:9.5px;line-height:1.7}
  .banner{margin-top:8px;font-family:ui-monospace,monospace;font-size:8.5px;letter-spacing:.1em;color:#12564f}
  .banner span{border:1px solid #ddd6cc;border-radius:3px;padding:2px 6px;margin-right:5px}
  .sec{margin-top:14px}
  .sec h2{font-size:11px;text-transform:uppercase;letter-spacing:.03em;color:#12564f;border-bottom:1px solid #ddd6cc;padding-bottom:3px;margin:0 0 6px}
  .score{display:inline-flex;align-items:baseline;gap:5px;background:${sevColor};color:#fff;padding:6px 12px;border-radius:5px}
  .score b{font-size:24px}
  .chip{background:${sevColor};color:#fff;font-family:ui-monospace,monospace;font-size:8.5px;text-transform:uppercase;padding:2px 6px;border-radius:3px}
  .kv{display:grid;grid-template-columns:1fr 1fr;gap:2px 20px;margin-top:8px}
  .kv div{display:flex;justify-content:space-between;border-bottom:1px dotted #ece7de;padding:2px 0}
  .kv .k{color:#57514a}.kv .v{font-weight:600}
  table{width:100%;border-collapse:collapse;font-size:10px}
  th{text-align:left;color:#57514a;font-size:8.5px;text-transform:uppercase;border-bottom:1px solid #ddd6cc;padding:3px 6px 3px 0}
  td{padding:3px 6px 3px 0;border-bottom:1px solid #ece7de;vertical-align:top}
  td.src{color:#12564f;font-weight:700;text-transform:uppercase;font-size:8.5px;width:12%}
  td.num{text-align:right}
  .invalid{border-left:3px solid #b31d1d;background:#f7f4ef;padding:8px 11px;color:#b31d1d;font-weight:600}
  .foot{margin-top:20px;border-top:1px solid #ddd6cc;padding-top:8px;color:#8a8279;font-size:8.5px}
</style></head><body>
<div class="head">
  <div style="display:flex;gap:9px;align-items:center">
    <span class="mark">HAWK&middot;EYE</span>
    <div><h1>Explainability Report</h1><div class="sub">Why this employee action was surfaced</div></div>
  </div>
  <div class="meta">Alert: <b class="mono">${esc(alert.alert_id)}</b><br>Generated: <b>${formatIST(new Date())}</b></div>
</div>
<div class="banner"><span>ALERT-ONLY</span><span>SYNTHETIC DATA</span><span>ON-PREM</span><span>CONFIDENTIAL</span></div>

<div class="sec"><h2>Risk posture</h2>
  <div style="display:flex;gap:12px;align-items:center;flex-wrap:wrap">
    <span class="score"><b>${Math.round(alert.risk_score)}</b> / 100</span>
    <span class="chip">${esc(alert.severity)}</span>
  </div>
  <div class="kv">
    <div><span class="k">Employee / entity</span><span class="v mono">${esc(alert.entity_id)}</span></div>
    <div><span class="k">Status</span><span class="v">${esc(statusLabel(alert.status))}</span></div>
    <div><span class="k">Confidence</span><span class="v">${formatPercent(alert.confidence * 100)}</span></div>
    <div><span class="k">Exposure</span><span class="v mono">${formatINR(alert.exposure_inr)}</span></div>
    <div><span class="k">Created (IST)</span><span class="v">${formatIST(alert.created_ts)}</span></div>
    <div><span class="k">SLA / TAT due</span><span class="v">${formatIST(alert.sla_due_ts)}</span></div>
  </div>
</div>

<div class="sec"><h2>Reason codes — the contestable basis</h2>
  ${
    reasons.length
      ? `<table><tbody>${reasons.map(reasonRow).join('')}</tbody></table>`
      : `<div class="invalid">INVALID — no reason codes. An alert without a contestable basis must not be actioned.</div>`
  }
</div>

<div class="sec"><h2>Feature attribution (SHAP · L3)</h2>
  ${
    shap.length
      ? `<table><thead><tr><th>Feature</th><th class="num">Contribution</th><th>Direction</th></tr></thead><tbody>${shap
          .map(
            (s) =>
              `<tr><td class="mono">${esc(s.feature)}</td><td class="num mono">${formatSigned(s.contribution)}</td><td>${s.contribution >= 0 ? 'Increases risk' : 'Decreases risk'}</td></tr>`,
          )
          .join('')}</tbody></table>`
      : '<div class="sub">No SHAP attribution returned.</div>'
  }
</div>

<div class="sec"><h2>Rule provenance (L1)</h2>
  ${
    rules.length
      ? `<table><thead><tr><th>Rule</th><th>Typology</th><th>Detail</th></tr></thead><tbody>${rules
          .map(
            (r) =>
              `<tr><td class="mono">${esc(r.code)}</td><td class="mono">${esc(r.typology ?? '—')}</td><td>${esc(r.detail)}</td></tr>`,
          )
          .join('')}</tbody></table>`
      : '<div class="sub">No deterministic rules fired.</div>'
  }
</div>

<div class="foot"><b>This report explains; it does not decide.</b> Hawk-Eye is alert-only — no automatic
action is taken; any block is a human request approved by a lead. Every view and PII unmask is audited.
Scores and reason codes come from detection layers L1–L6 on synthetic, on-prem data.</div>
</body></html>`
}

export function AlertReportButton({ alertId, className }: { alertId: string; className?: string }) {
  const [loading, setLoading] = useState(false)

  const handle = async () => {
    setLoading(true)
    try {
      const alert = await apiClient.getAlert(alertId)
      const explanation = await apiClient.getExplanation(alertId).catch(() => null)
      const w = window.open('', '_blank', 'width=900,height=1000')
      if (!w) {
        toast.error('Allow pop-ups to download the report')
        return
      }
      w.document.write(buildReportHtml(alert, explanation))
      w.document.close()
      w.focus()
      // Give the new window a beat to lay out fonts before the print dialog.
      setTimeout(() => w.print(), 350)
    } catch {
      toast.error('Could not build the explainability report')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Button
      variant="outline"
      size="sm"
      className={cn('h-8 gap-1.5', className)}
      onClick={handle}
      disabled={loading}
      aria-label="Download PDF"
    >
      {loading ? <Loader2 className="size-3.5 animate-spin" /> : <FileDown className="size-3.5" />}
      Download PDF
    </Button>
  )
}
