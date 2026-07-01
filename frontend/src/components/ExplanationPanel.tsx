/**
 * Explanation panel (Blueprint Part 11 / Part 24.4 §4 / Part 25) — the "why" behind a fused alert,
 * assembled so it is SAR / FMR-defensible. One fetch (`getExplanation`) drives four evidence
 * sections; the AI narrative is a fifth, separately-fetched section that is clearly labelled and
 * never authoritative:
 *   1. SHAP attribution     — signed per-feature push on the score (L3 / GBDT).
 *   2. Rule provenance      — the deterministic SoD / typology rules that fired (L1).
 *   3. Sequence attention   — which actions the sequence model weighed (L4 / LAXCAT).
 *   4. Graph evidence       — the ring / GNNExplainer subgraph (L5).
 *   5. AI narrative         — a plain-language reading aid (Part 25). AI explains; L1–L6 decide.
 */
import { useQuery } from '@tanstack/react-query'
import {
  BarChartHorizontal,
  ScrollText,
  Activity,
  Share2,
  Sparkles,
  GitBranch,
  Crosshair,
  Download,
  BadgeCheck,
  Fingerprint,
  ShieldAlert,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { apiClient } from '@/lib/apiClient'
import { queryKeys } from '@/lib/queryKeys'
import { cn } from '@/lib/cn'
import { humanize, formatPercent } from '@/lib/format'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { Skeleton } from '@/components/ui/skeleton'
import { EmptyState } from '@/components/ui/empty-state'
import { QueryBoundary } from '@/components/QueryBoundary'
import { ShapChart } from '@/components/ShapChart'
import { RuleProvenance } from '@/components/RuleProvenance'
import { AttentionView } from '@/components/AttentionView'
import { AiNarrative } from '@/components/AiNarrative'
import { ScoreComposition } from '@/components/ScoreComposition'
import { ProvenanceBadge } from '@/components/ProvenanceBadge'
import type { GraphEvidence, ModelLineageEntry } from '@/lib/types'

/* ── Section chrome ─────────────────────────────────────────────────────── */
function Section({
  icon: Icon,
  title,
  meta,
  description,
  children,
}: {
  icon: typeof ScrollText
  title: string
  meta?: React.ReactNode
  description?: string
  children: React.ReactNode
}) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle className="flex items-center gap-2">
            <Icon className="size-4 text-muted-foreground" />
            {title}
          </CardTitle>
          {meta}
        </div>
        {description ? <p className="text-xs text-muted-foreground">{description}</p> : null}
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  )
}

/* ── Graph evidence summary (section 4) ─────────────────────────────────── */
function GraphEvidenceSummary({ graph }: { graph: GraphEvidence }) {
  const topNodes = [...graph.nodes]
    .sort((a, b) => (b.importance ?? 0) - (a.importance ?? 0))
    .slice(0, 6)
  const topEdges = [...graph.edges]
    .sort((a, b) => (b.importance ?? 0) - (a.importance ?? 0))
    .slice(0, 6)

  return (
    <div className="space-y-3">
      <p className="text-sm leading-relaxed text-foreground">{graph.summary}</p>

      {topNodes.length > 0 ? (
        <div>
          <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Key nodes
          </h4>
          <ul className="mt-1 flex flex-wrap gap-1.5">
            {topNodes.map((n) => (
              <li
                key={n.id}
                className="inline-flex items-center gap-1.5 rounded-md border border-border bg-muted/30 px-2 py-0.5 text-xs"
                title={n.id}
              >
                <span className="font-medium">{n.label}</span>
                <span className="text-muted-foreground">{humanize(n.type)}</span>
                {n.importance != null ? (
                  <span className="tabular-nums text-reason-graph">
                    {formatPercent(n.importance)}
                  </span>
                ) : null}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {topEdges.length > 0 ? (
        <div>
          <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Key links
          </h4>
          <ul className="mt-1 space-y-1">
            {topEdges.map((e, i) => (
              <li
                key={`${e.source}-${e.target}-${i}`}
                className="flex items-center gap-1.5 text-xs"
              >
                <span className="font-mono text-foreground">{e.source}</span>
                <GitBranch className="size-3 shrink-0 text-reason-graph" />
                <span className="font-mono text-foreground">{e.target}</span>
                <Badge variant="muted" className="ml-1 text-[0.7rem]">
                  {humanize(e.type)}
                </Badge>
                {e.importance != null ? (
                  <span className="tabular-nums text-muted-foreground">
                    {formatPercent(e.importance)}
                  </span>
                ) : null}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  )
}

/* ── Model lineage (section 4.5) — which model produced each layer + governance posture ─────── */
function ModelLineageSection({ lineage }: { lineage: ModelLineageEntry[] }) {
  const signed = lineage.filter((l) => l.signed).length
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <Fingerprint className="size-3.5" />
        Which model produced each layer&apos;s score — and its governance posture (stage · MRMF risk
        tier · signature · sign-off).
      </div>
      <ul className="divide-y divide-border/60 rounded-lg border border-border/60">
        {lineage.map((l) => (
          <li key={`${l.layer}-${l.model_id}`} className="flex items-center gap-2 px-2.5 py-1.5 text-xs">
            <span className="w-24 shrink-0 truncate font-mono text-foreground" title={l.layer}>
              {l.layer}
            </span>
            <span className="min-w-0 flex-1 truncate">
              <span className="font-medium text-foreground">{l.model_id}</span>{' '}
              <span className="font-mono text-2xs text-muted-foreground">{l.version}</span>
            </span>
            <span className="hidden shrink-0 rounded bg-muted px-1.5 py-0.5 font-mono text-[0.6rem] text-muted-foreground sm:inline">
              {l.stage}
            </span>
            {l.risk_tier ? (
              <span className="hidden shrink-0 text-[0.6rem] text-muted-foreground md:inline">
                {l.risk_tier}
              </span>
            ) : null}
            {l.signed ? (
              <BadgeCheck className="size-3.5 shrink-0 text-severity-high" aria-label="signature verified" />
            ) : (
              <ShieldAlert className="size-3.5 shrink-0 text-severity-medium" aria-label="unsigned" />
            )}
          </li>
        ))}
      </ul>
      <p className="text-[0.7rem] text-muted-foreground">
        <span className="font-mono tabular-nums text-foreground">
          {signed}/{lineage.length}
        </span>{' '}
        artifacts signature-verified · reproducible: this alert can be re-scored on the exact model
        versions above.
      </p>
    </div>
  )
}

/* ── Narrative trust panel (Part 25) ────────────────────────────────────────
 * Shares the narrative query (same key as AiNarrative, so react-query dedupes the fetch) purely to
 * read its attestation state, then expands the TEE badge into the ProvenanceBadge trust panel —
 * verifiable detail when attested, an honest "standard cloud inference" line when not.
 */
function NarrativeProvenance({ alertId }: { alertId: string }) {
  const query = useQuery({
    queryKey: queryKeys.narrative(alertId),
    queryFn: () => apiClient.getNarrative(alertId),
  })
  if (!query.data) return null
  return (
    <div className="mt-3">
      <ProvenanceBadge alertId={alertId} attested={query.data.tee_attested} />
    </div>
  )
}

/* ── Loading skeleton ───────────────────────────────────────────────────── */
function PanelSkeleton() {
  return (
    <div className="space-y-3">
      {Array.from({ length: 3 }).map((_, i) => (
        <Card key={i}>
          <CardHeader className="pb-2">
            <Skeleton className="h-5 w-40" />
          </CardHeader>
          <CardContent className="space-y-2">
            <Skeleton className="h-24 w-full" />
          </CardContent>
        </Card>
      ))}
    </div>
  )
}

/** Fetch the audit-grade explainability report and save it as a JSON file (SAR/FMR evidence pack). */
async function downloadExplanationReport(alertId: string): Promise<void> {
  try {
    const report = await apiClient.getExplanationReport(alertId)
    const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `explainability-${alertId}.json`
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  } catch {
    /* the button is best-effort; failures are silent (the panel still shows the evidence) */
  }
}

export function ExplanationPanel({ alertId }: { alertId: string }) {
  const query = useQuery({
    queryKey: queryKeys.explanation(alertId),
    queryFn: () => apiClient.getExplanation(alertId),
  })

  const data = query.data
  const ruleCount = data?.rules.length ?? 0
  const shapCount = data?.shap.length ?? 0
  const attentionCount = data?.attention.filter((s) => s.steps.length > 0).length ?? 0

  return (
    <section className="space-y-3" aria-label="Alert explanation">
      <div className="flex items-center gap-2">
        <h2 className="text-sm font-semibold tracking-tight">Why this alert fired</h2>
        <Badge variant="outline" className="text-[0.7rem] text-muted-foreground">
          SAR / FMR-defensible evidence
        </Badge>
        <Button
          variant="outline"
          size="sm"
          className="ml-auto h-7 gap-1.5"
          onClick={() => void downloadExplanationReport(alertId)}
        >
          <Download className="size-3.5" />
          Report
        </Button>
      </div>

      <QueryBoundary
        isLoading={query.isLoading}
        isError={query.isError}
        error={query.error}
        onRetry={() => void query.refetch()}
        skeleton={<PanelSkeleton />}
      >
        {data ? (
          <div className="space-y-3">
            {/* 0 · Score composition — the headline "why this fired" (L6 fusion vs threshold). */}
            {data.fusion ? (
              <Section
                icon={Crosshair}
                title="Why this fired"
                description="Fused L6 score against the decision threshold, decomposed into the layer contributions the fusion meta-learner weighed."
              >
                <ScoreComposition fusion={data.fusion} />
              </Section>
            ) : null}

            {/* 1 · SHAP feature attribution */}
            <Section
              icon={BarChartHorizontal}
              title="Feature attribution"
              description="Signed SHAP contribution of each feature to the fused risk score (L3 · GBDT)."
              meta={
                shapCount > 0 ? (
                  <Badge variant="secondary" className="text-[0.7rem]">
                    {shapCount} features
                  </Badge>
                ) : null
              }
            >
              <ShapChart features={data.shap} />
            </Section>

            {/* 2 · Rule provenance */}
            <Section
              icon={ScrollText}
              title="Rule provenance"
              description="Deterministic SoD / typology rules that fired (L1)."
              meta={
                ruleCount > 0 ? (
                  <Badge variant="secondary" className="text-[0.7rem]">
                    {ruleCount} fired
                  </Badge>
                ) : null
              }
            >
              <RuleProvenance rules={data.rules} />
            </Section>

            {/* 3 · Sequence attention */}
            <Section
              icon={Activity}
              title="Sequence attention"
              description="Steps the sequence model weighed within the behavioural session (L4 · LAXCAT)."
              meta={
                attentionCount > 0 ? (
                  <Badge variant="secondary" className="text-[0.7rem]">
                    {attentionCount} {attentionCount === 1 ? 'session' : 'sessions'}
                  </Badge>
                ) : null
              }
            >
              <AttentionView sessions={data.attention} />
            </Section>

            {/* 4 · Graph evidence */}
            <Section
              icon={Share2}
              title="Graph evidence"
              description="Collusion ring / subgraph the graph model surfaced (L5)."
              meta={
                <div className="flex items-center gap-1.5">
                  {data.graph?.explainer_model ? (
                    <Badge variant="muted" className="text-[0.7rem]">
                      {data.graph.explainer_model}
                    </Badge>
                  ) : null}
                  {data.graph?.ring_id ? (
                    <Badge variant="outline" className="font-mono text-[0.7rem] text-reason-graph">
                      {data.graph.ring_id}
                    </Badge>
                  ) : null}
                </div>
              }
            >
              {data.graph ? (
                <GraphEvidenceSummary graph={data.graph} />
              ) : (
                <EmptyState
                  icon={Share2}
                  title="No graph evidence"
                  description="The graph layer (L5) did not contribute a subgraph for this alert."
                />
              )}
            </Section>

            {/* 4.5 · Model lineage — per-layer model provenance + governance posture (Part 23/34) */}
            {data.model_lineage && data.model_lineage.length > 0 ? (
              <Section
                icon={Fingerprint}
                title="Model lineage & provenance"
                description="Which model version produced each layer's score, and whether it is signed and signed-off — the reproducibility trail for audit."
                meta={
                  <Badge variant="muted" className="text-[0.7rem]">
                    {data.model_lineage.filter((l) => l.signed).length}/{data.model_lineage.length} signed
                  </Badge>
                }
              >
                <ModelLineageSection lineage={data.model_lineage} />
              </Section>
            ) : null}

            {/* 5 · AI narrative — clearly labelled, never authoritative */}
            <Card className={cn('border-ai/30')}>
              <CardHeader className="pb-2">
                <CardTitle className="flex items-center gap-2">
                  <Sparkles className="size-4 text-ai" />
                  AI narrative
                </CardTitle>
                <p className="text-xs text-muted-foreground">
                  Plain-language summary of the evidence above (Part 25).
                </p>
              </CardHeader>
              <CardContent>
                <Separator className="mb-3" />
                <AiNarrative alertId={alertId} />
                {/* Trust panel — expand the TEE badge into verifiable attestation detail. */}
                <NarrativeProvenance alertId={alertId} />
              </CardContent>
            </Card>
          </div>
        ) : (
          <EmptyState
            icon={ScrollText}
            title="No explanation available"
            description="No model attribution was returned for this alert."
          />
        )}
      </QueryBoundary>
    </section>
  )
}
