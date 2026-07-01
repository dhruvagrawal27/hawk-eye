/**
 * Rule provenance — the deterministic L1 reasons that fired, shown so an investigator (and an
 * auditor) can see *exactly which SoD / typology rule* triggered. Each item carries its code,
 * plain-language detail, typology family, SoD rule and severity. (Blueprint Part 11 / Part 24.4 §4.)
 */
import { ScrollText, ShieldAlert } from 'lucide-react'
import { cn } from '@/lib/cn'
import { humanize, layerLabel } from '@/lib/format'
import { Badge } from '@/components/ui/badge'
import { SeverityBadge, ReasonSourceBadge } from '@/components/badges'
import { EmptyState } from '@/components/ui/empty-state'
import { useAutoAnimateList } from '@/ui'
import type { RuleProvenanceItem } from '@/lib/types'

export function RuleProvenance({ rules }: { rules: RuleProvenanceItem[] }) {
  const [listRef] = useAutoAnimateList<HTMLUListElement>()

  if (rules.length === 0) {
    return (
      <EmptyState
        icon={ScrollText}
        title="No deterministic rules fired"
        description="This alert was raised by statistical / graph layers (L2–L5) rather than an L1 rule. See SHAP and graph evidence."
      />
    )
  }

  return (
    <ul ref={listRef} className="space-y-2">
      {rules.map((rule, i) => (
        <li key={`${rule.code}-${i}`} className="rounded-lg border border-border bg-muted/30 p-3">
          <div className="flex flex-wrap items-center gap-2">
            <ReasonSourceBadge source="rule" />
            <code className="rounded bg-background px-1.5 py-0.5 font-mono text-xs font-semibold text-reason-rule">
              {rule.code}
            </code>
            {rule.severity ? <SeverityBadge severity={rule.severity} /> : null}
            {rule.layer ? (
              <Badge variant="muted" className="font-mono text-[0.7rem]">
                {layerLabel(rule.layer)}
              </Badge>
            ) : null}
          </div>

          <p className="mt-1.5 text-sm text-foreground">{rule.detail}</p>

          {rule.typology || rule.sod_rule ? (
            <dl className="mt-2 flex flex-wrap gap-x-6 gap-y-1 text-xs">
              {rule.typology ? (
                <div className="flex items-center gap-1.5">
                  <dt className="text-muted-foreground">Typology</dt>
                  <dd>
                    <Badge variant="outline" className="font-medium">
                      {humanize(rule.typology)}
                    </Badge>
                  </dd>
                </div>
              ) : null}
              {rule.sod_rule ? (
                <div className="flex items-center gap-1.5">
                  <dt className="flex items-center gap-1 text-muted-foreground">
                    <ShieldAlert className={cn('size-3.5 text-severity-high')} /> SoD rule
                  </dt>
                  <dd className="font-mono text-foreground">{rule.sod_rule}</dd>
                </div>
              ) : null}
            </dl>
          ) : null}
        </li>
      ))}
    </ul>
  )
}
