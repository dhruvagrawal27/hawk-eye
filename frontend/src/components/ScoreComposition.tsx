/**
 * Score composition — the headline "why this alert fired" (Blueprint Part 11 / Part 24.4 §4). It sits
 * at the TOP of the explanation panel, above the SHAP detail, and answers the question a reviewer
 * asks first: *did the system clear the bar, and which layer pushed it over?*
 *
 * It shows the fused L6 score against the decision threshold, then decomposes the fusion into the
 * per-layer contributions the meta-learner weighed (L3 GBDT · L5 graph · L2 unsupervised) as labelled
 * width bars. When the supervised GBDT layer alone would have *missed* the alert but graph fusion
 * carried it over the line, a "rescued by graph fusion" insight is surfaced — computed client-side.
 *
 * AI explains; L1–L6 decide. This panel is L6 arithmetic, not narrative — it is authoritative.
 */
import { Activity, GitBranch, Gavel, Network, Sparkles, ShieldCheck, Info } from 'lucide-react'
import { cn } from '@/lib/cn'
import { humanize } from '@/lib/format'
import { riskColor, riskLevelFromScore, RISK_TEXT } from '@/lib/risk'
import type { FusionBreakdown, FusionComponent, FusionLayer } from '@/lib/types'

/**
 * Fusion meta-learner coefficients + decision threshold — the single source of truth for the L6
 * blend. THRESHOLD is on the same 0–1 scale the fusion outputs; the calibrated 0–100 score is
 * `fused * 100`. Kept here as one const so the "rescued by graph fusion" derivation and any
 * synthesised fixture agree. (Blueprint Part 11 fusion stack.)
 */
export const THRESHOLD = 0.7 // fallback decision threshold on the 0–1 scale; backend supplies the real one
export const FUSION_WEIGHTS: Record<FusionLayer, number> = {
  L1_rule: 1.7,
  L2_unsupervised: 1.2,
  L3_gbdt: 2.4,
  L4_sequence: 1.0,
  L5_graph: 1.2,
}

/** Per-layer presentation chrome (icon + accent), keyed by the fusion layer code. */
const LAYER_META: Record<
  string,
  { icon: typeof GitBranch; defaultLabel: string; defaultSub: string; accent: string }
> = {
  L1_rule: {
    icon: Gavel,
    defaultLabel: 'Rules / BRE',
    defaultSub: 'L1 · deterministic',
    accent: 'var(--reason-rule)',
  },
  L2_unsupervised: {
    icon: Sparkles,
    defaultLabel: 'Anomaly',
    defaultSub: 'L2 · unsupervised',
    accent: 'var(--severity-medium)',
  },
  L3_gbdt: {
    icon: GitBranch,
    defaultLabel: 'Gradient-boosted trees',
    defaultSub: 'L3 · supervised tabular',
    accent: 'var(--reason-shap)',
  },
  L4_sequence: {
    icon: Activity,
    defaultLabel: 'Sequence',
    defaultSub: 'L4 · attention',
    accent: 'var(--ai)',
  },
  L5_graph: {
    icon: Network,
    defaultLabel: 'Graph / collusion',
    defaultSub: 'L5 · GNN',
    accent: 'var(--reason-graph)',
  },
}

/**
 * Was this alert "rescued by graph fusion"? True when the supervised GBDT layer on its own would
 * have fallen below the decision threshold, but the fused score cleared it — i.e. the non-GBDT
 * layers (graph especially) are what carried the alert over the line.
 */
export function computeRescued(fusion: FusionBreakdown): boolean {
  if (typeof fusion.rescued === 'boolean') return fusion.rescued // trust the backend's arithmetic
  const gbdt = fusion.components.find((c) => c.layer === 'L3_gbdt')
  if (!gbdt || gbdt.proba == null) return false
  return gbdt.proba < fusion.threshold && fusion.fused >= fusion.threshold
}

/** The layer the backend named as decisive, else the strongest weighted non-GBDT contributor. */
function decisiveComponent(fusion: FusionBreakdown): FusionComponent | undefined {
  if (fusion.decisive_layer) {
    const named = fusion.components.find((c) => c.layer === fusion.decisive_layer)
    if (named) return named
  }
  const fired = fusion.components.filter((c) => c.proba != null && c.layer !== 'L3_gbdt')
  if (!fired.length) return undefined
  return fired.reduce((a, b) =>
    (b.contribution ?? b.weight * (b.proba as number)) >
    (a.contribution ?? a.weight * (a.proba as number))
      ? b
      : a,
  )
}

/* ── Small callout used for the "rescued by graph fusion" insight ─────────── */
function InsightCallout({
  icon: Icon,
  title,
  children,
  tone = 'graph',
}: {
  icon: typeof ShieldCheck
  title: string
  children: React.ReactNode
  tone?: 'graph' | 'info'
}) {
  const toneClass =
    tone === 'graph'
      ? 'border-reason-graph/30 bg-reason-graph/10 text-reason-graph'
      : 'border-border bg-muted/40 text-muted-foreground'
  return (
    <div className={cn('flex items-start gap-2 rounded-lg border px-3 py-2 text-xs', toneClass)}>
      <Icon className="mt-0.5 size-4 shrink-0" />
      <div className="min-w-0 space-y-0.5">
        <p className="font-semibold">{title}</p>
        <p className="leading-relaxed text-foreground/80">{children}</p>
      </div>
    </div>
  )
}

/* ── One layer contribution bar ───────────────────────────────────────────── */
function LayerBar({ component, maxWeighted }: { component: FusionComponent; maxWeighted: number }) {
  const meta = LAYER_META[component.layer] ?? {
    icon: Sparkles,
    defaultLabel: humanize(String(component.layer)),
    defaultSub: String(component.layer),
    accent: 'var(--severity-medium)',
  }
  const Icon = meta.icon
  const fired = component.proba != null
  // Bar length encodes the layer's weighted pull on the fused score (weight × proba), normalised to
  // the strongest contributor so the dominant driver fills the track.
  const weighted = fired ? component.weight * (component.proba as number) : 0
  const pct = maxWeighted > 0 ? Math.round((weighted / maxWeighted) * 100) : 0

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between gap-2 text-xs">
        <span className="flex min-w-0 items-center gap-1.5">
          <Icon
            className="size-3.5 shrink-0"
            style={{ color: `hsl(${meta.accent})` }}
            aria-hidden
          />
          <span className="truncate font-medium text-foreground">
            {component.label || meta.defaultLabel}
          </span>
          <span className="hidden truncate text-muted-foreground sm:inline">
            {component.sublabel || meta.defaultSub}
          </span>
        </span>
        <span className="shrink-0 tabular-nums text-muted-foreground">
          {fired ? (
            <>
              <span className="text-foreground">
                {Math.round((component.proba as number) * 100)}
              </span>
              <span className="mx-1 opacity-50">×</span>
              <span>{component.weight.toFixed(2)}</span>
            </>
          ) : (
            <span className="italic">did not fire</span>
          )}
        </span>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
        <div
          className={cn('h-full rounded-full transition-[width]', !fired && 'opacity-30')}
          style={{
            width: `${fired ? Math.max(pct, 2) : 0}%`,
            backgroundColor: `hsl(${meta.accent})`,
          }}
        />
      </div>
    </div>
  )
}

/* ── Fused score vs threshold meter ───────────────────────────────────────── */
function FusedMeter({
  fused,
  threshold,
  hardHit = false,
}: {
  fused: number
  threshold: number
  hardHit?: boolean
}) {
  const score = Math.round(fused * 100)
  const level = riskLevelFromScore(score)
  const thresholdPct = Math.min(100, Math.max(0, threshold * 100))
  // A hard-hit (deterministic hard rule) is emitted regardless of the fused meter — so even when the
  // fused score sits under the bar, the alert is a legitimate must-review, not a false positive.
  const cleared = fused >= threshold
  const emitted = cleared || hardHit

  return (
    <div className="space-y-2">
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Fused risk (L6)
        </span>
        <span className="flex items-baseline gap-1.5">
          <span className={cn('text-2xl font-bold tabular-nums', RISK_TEXT[level])}>{score}</span>
          <span className="text-xs text-muted-foreground">/ 100</span>
        </span>
      </div>

      {/* Track with the score fill and the threshold tick. */}
      <div className="relative h-3 w-full overflow-hidden rounded-full bg-muted">
        <div
          className="h-full rounded-full"
          style={{ width: `${Math.max(2, score)}%`, backgroundColor: riskColor(score) }}
        />
        <div
          className="absolute inset-y-0 w-px bg-foreground/70"
          style={{ left: `${thresholdPct}%` }}
          aria-hidden
        />
        <div
          className="absolute -top-0.5 size-1.5 -translate-x-1/2 rotate-45 bg-foreground/70"
          style={{ left: `${thresholdPct}%` }}
          aria-hidden
        />
      </div>

      <div className="flex items-center justify-between text-[0.7rem] text-muted-foreground">
        <span>
          Decision threshold{' '}
          <span className="font-mono tabular-nums text-foreground">{Math.round(thresholdPct)}</span>
        </span>
        <span
          className={cn(
            'inline-flex items-center gap-1 font-medium',
            emitted ? 'text-severity-high' : 'text-sla-ok',
          )}
          title={
            hardHit && !cleared
              ? 'A deterministic hard rule fired — the alert is emitted for review regardless of the fused meter.'
              : undefined
          }
        >
          {cleared
            ? 'cleared the bar'
            : hardHit
              ? 'hard-rule alert (emitted regardless)'
              : 'below threshold'}
        </span>
      </div>
    </div>
  )
}

/** Cross-layer agreement bar — a tight spread across layers is a stronger, more trustworthy signal. */
function AgreementReadout({ agreement }: { agreement: number }) {
  const pct = Math.round(agreement * 100)
  const label = agreement >= 0.75 ? 'strong concurrence' : agreement >= 0.45 ? 'partial' : 'divergent'
  const tone =
    agreement >= 0.75
      ? 'var(--severity-high)'
      : agreement >= 0.45
        ? 'var(--severity-medium)'
        : 'var(--muted-foreground)'
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-xs">
        <span className="font-semibold uppercase tracking-wide text-muted-foreground">
          Cross-layer agreement
        </span>
        <span className="tabular-nums text-muted-foreground">
          <span className="text-foreground">{pct}</span> · {label}
        </span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
        <div
          className="h-full rounded-full transition-[width]"
          style={{ width: `${Math.max(2, pct)}%`, backgroundColor: `hsl(${tone})` }}
        />
      </div>
    </div>
  )
}

export function ScoreComposition({ fusion }: { fusion: FusionBreakdown }) {
  const rescued = computeRescued(fusion)
  const gbdt = fusion.components.find((c) => c.layer === 'L3_gbdt')
  const decisive = decisiveComponent(fusion)
  const maxWeighted = Math.max(
    ...fusion.components.map((c) => (c.proba != null ? c.weight * c.proba : 0)),
    0.0001,
  )

  return (
    <div className="space-y-4">
      <FusedMeter fused={fusion.fused} threshold={fusion.threshold} hardHit={fusion.hard_hit} />

      {typeof fusion.agreement === 'number' && <AgreementReadout agreement={fusion.agreement} />}

      <div className="space-y-2.5">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Per-layer contribution
        </p>
        {fusion.components.map((c) => (
          <LayerBar key={String(c.layer)} component={c} maxWeighted={maxWeighted} />
        ))}
      </div>

      {rescued && gbdt?.proba != null && decisive ? (
        <InsightCallout icon={ShieldCheck} title={`Rescued by ${decisive.label}`}>
          The supervised model (GBDT) scored{' '}
          <span className="font-mono tabular-nums">{Math.round(gbdt.proba * 100)}</span> — below the
          decision threshold of{' '}
          <span className="font-mono tabular-nums">{Math.round(fusion.threshold * 100)}</span> — and
          on its own would have missed this. {decisive.label} ({String(decisive.layer)}) carried the
          fused score over the line. This is exactly the cross-layer signal a single tabular model
          cannot see.
        </InsightCallout>
      ) : (
        <InsightCallout icon={Info} title="How to read this" tone="info">
          Bars show each layer&apos;s weighted pull (its output × the fusion coefficient) on the
          final score. The fused L6 score — not any single layer — is what crossed the threshold.
          {decisive && (
            <>
              {' '}
              Strongest driver: <span className="font-medium text-foreground">{decisive.label}</span>
              .
            </>
          )}
        </InsightCallout>
      )}
    </div>
  )
}
