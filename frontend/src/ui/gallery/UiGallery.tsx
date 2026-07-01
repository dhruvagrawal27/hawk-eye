/**
 * /ui-gallery — the "Daylight Forensics" kit on one page (mock-only, dev reference).
 *
 * Renders every design token (with a **live** WCAG contrast readout computed from the app's own CSS
 * variables) and every signature primitive, so Agents B and C can see the whole system at a glance and
 * verify AA. Not part of the product surface — a top-level route outside the auth shell.
 */
import { useEffect, useMemo, useState } from 'react'
import {
  RiskGauge,
  AmountFlip,
  CountUp,
  SlaRing,
  Sparkline,
  PeerStrip,
  HashChainBlock,
  EventTicker,
  PaperField,
  RouteTransition,
  staggerParent,
  staggerItem,
  useMagnetic,
  m,
  type TickerItem,
  type RiskLevel,
} from '@/ui'
import { contrastRatio, wcagRating, readToken } from './contrast'
import { cn } from '@/lib/cn'

/* ── token catalogue (name → CSS var) ─────────────────────────────────────── */
const CANVAS = [
  ['Porcelain (bg)', '--background'],
  ['Bone (card)', '--card'],
  ['Paper (muted)', '--muted'],
  ['Teal-wash (accent)', '--accent'],
] as const
const INK = [
  ['Ink', '--foreground'],
  ['Ink-muted', '--muted-foreground'],
] as const
const BRAND = [['Ink-teal (primary)', '--primary']] as const
const RISK = [
  ['Low', '--severity-low'],
  ['Medium', '--severity-medium'],
  ['High', '--severity-high'],
  ['Critical', '--severity-critical'],
  ['Info', '--severity-info'],
] as const
const SLA = [
  ['SLA ok', '--sla-ok'],
  ['SLA warn', '--sla-warn'],
  ['SLA urgent', '--sla-urgent'],
  ['SLA breached', '--sla-breached'],
] as const
const PROVENANCE = [
  ['Reason · rule', '--reason-rule'],
  ['Reason · shap', '--reason-shap'],
  ['Reason · graph', '--reason-graph'],
  ['AI', '--ai'],
  ['TEE', '--tee'],
] as const

function Section({
  eyebrow,
  title,
  children,
}: {
  eyebrow: string
  title: string
  children: React.ReactNode
}) {
  return (
    <section className="border-t border-border py-8">
      <p className="font-mono text-2xs uppercase tracking-widest text-primary">{eyebrow}</p>
      <h2 className="mt-1 font-display text-2xl font-semibold text-foreground">{title}</h2>
      <div className="mt-5">{children}</div>
    </section>
  )
}

function Swatch({
  name,
  varName,
  bgVar,
  surface = false,
}: {
  name: string
  varName: string
  bgVar: string
  /** A canvas plane: rate INK legibility ON it, not the plane against another plane. */
  surface?: boolean
}) {
  const [ratio, setRatio] = useState<number | null>(null)
  useEffect(() => {
    // Foreground token → colour on the reference surface; surface token → ink on the surface.
    const fg = readToken(surface ? '--foreground' : varName)
    const bg = readToken(surface ? varName : bgVar)
    if (fg && bg) setRatio(contrastRatio(fg, bg))
  }, [varName, bgVar, surface])
  const rating = ratio ? wcagRating(ratio) : null
  return (
    <div className="overflow-hidden rounded-md border border-border bg-card">
      <div
        className="flex h-16 items-center justify-center"
        style={{ background: surface ? `hsl(var(${varName}))` : `hsl(var(${bgVar}))` }}
      >
        {surface ? (
          <span className="font-display text-lg text-foreground">Aa</span>
        ) : (
          <span
            className="h-8 w-8 rounded-full border border-border"
            style={{ background: `hsl(var(${varName}))` }}
          />
        )}
      </div>
      <div className="space-y-0.5 px-2.5 py-2">
        <div className="text-xs font-medium text-foreground">{name}</div>
        <div className="font-mono text-3xs text-muted-foreground">{varName}</div>
        {ratio ? (
          <div className="flex items-center justify-between font-mono text-3xs">
            <span className="text-muted-foreground">
              {surface ? 'ink ' : ''}
              {ratio.toFixed(2)}:1
            </span>
            <span
              className={cn(
                'rounded px-1 font-semibold',
                rating === 'Fail'
                  ? 'bg-severity-critical/15 text-severity-critical'
                  : 'bg-tee/15 text-tee',
              )}
            >
              {rating}
            </span>
          </div>
        ) : null}
      </div>
    </div>
  )
}

const SPARK = [4, 9, 6, 11, 7, 14, 10, 18, 13, 22, 19, 28]

export function UiGallery() {
  const [nonce, setNonce] = useState(0)
  const magnetic = useMagnetic(8)

  // A gentle synthetic event tape (mock-only; browser timers are fine on this dev route).
  const [ticks, setTicks] = useState<TickerItem[]>(() => seedTicks())
  useEffect(() => {
    const id = window.setInterval(() => {
      setTicks((prev) => [makeTick(prev.length), ...prev].slice(0, 14))
    }, 1600)
    return () => window.clearInterval(id)
  }, [])

  const now = useMemo(() => new Date(), [])
  const due = (days: number) => new Date(now.getTime() + days * 86_400_000).toISOString()

  return (
    <RouteTransition className="min-h-screen bg-background">
      <div className="mx-auto max-w-6xl px-6 py-10">
        <header className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="font-mono text-2xs uppercase tracking-widest text-primary">
              Hawk-Eye · design system
            </p>
            <h1 className="mt-1 font-display text-4xl font-semibold tracking-tight text-foreground">
              Daylight Forensics
            </h1>
            <p className="mt-2 max-w-xl text-sm text-muted-foreground">
              The token + motion + primitive kit. Contrast ratios below are computed live from the
              app&apos;s CSS variables — every colour clears WCAG AA on its own surface.
            </p>
          </div>
          <button
            ref={magnetic.ref}
            style={magnetic.style}
            onMouseMove={magnetic.onMouseMove}
            onMouseLeave={magnetic.onMouseLeave}
            onClick={() => setNonce((n) => n + 1)}
            className="focus-ring rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow-dossier"
          >
            Re-roll animations
          </button>
        </header>

        {/* ── Tokens ─────────────────────────────────────────────── */}
        <Section eyebrow="01 · tokens" title="Canvas, ink & accent">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {CANVAS.map(([n, v]) => (
              <Swatch key={v} name={n} varName={v} bgVar="--background" surface />
            ))}
            {INK.map(([n, v]) => (
              <Swatch key={v} name={n} varName={v} bgVar="--background" />
            ))}
            {BRAND.map(([n, v]) => (
              <Swatch key={v} name={n} varName={v} bgVar="--background" />
            ))}
          </div>
        </Section>

        <Section eyebrow="02 · risk ramp" title="Sacred risk ramp (colorblind-safe)">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
            {RISK.map(([n, v]) => (
              <Swatch key={v} name={n} varName={v} bgVar="--background" />
            ))}
          </div>
        </Section>

        <Section eyebrow="03 · bands" title="SLA bands · reason-code provenance · AI/TEE">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-5">
            {[...SLA, ...PROVENANCE].map(([n, v]) => (
              <Swatch key={v} name={n} varName={v} bgVar="--card" />
            ))}
          </div>
        </Section>

        {/* ── Typography ─────────────────────────────────────────── */}
        <Section eyebrow="04 · type" title="Three voices">
          <div className="space-y-4">
            <div className="rounded-md border border-border bg-card p-4">
              <p className="text-2xs uppercase tracking-widest text-muted-foreground">
                Display · Fraunces
              </p>
              <p className="font-display text-3xl font-semibold text-foreground">
                A human always decides.
              </p>
            </div>
            <div className="rounded-md border border-border bg-card p-4">
              <p className="text-2xs uppercase tracking-widest text-muted-foreground">
                Body · Inter
              </p>
              <p className="text-base text-foreground">
                Alert-only fraud detection for privileged users — the console surfaces risk, never
                acts on it.
              </p>
            </div>
            <div className="rounded-md border border-border bg-card p-4">
              <p className="text-2xs uppercase tracking-widest text-muted-foreground">
                Evidence · JetBrains Mono
              </p>
              <p className="font-mono text-base tabular-nums text-foreground">
                EMP-7f3a · ACCT-4d22 · 2026-06-30T14:22:07 · ₹1,20,00,000 · 0x9f3a…e11c
              </p>
            </div>
          </div>
        </Section>

        {/* ── Primitives ─────────────────────────────────────────── */}
        <Section eyebrow="05 · primitives" title="RiskGauge">
          <div key={`gauge-${nonce}`} className="flex flex-wrap items-end gap-8">
            <RiskGauge score={92} confidence={0.86} size="lg" label="risk" />
            <RiskGauge score={61} confidence={0.55} size="md" label="risk" />
            <RiskGauge score={28} size="sm" label="low" />
            <RiskGauge score={7.4} max={10} size="md" label="ring score" />
          </div>
        </Section>

        <Section eyebrow="06 · primitives" title="AmountFlip · CountUp">
          <div key={`num-${nonce}`} className="flex flex-wrap items-center gap-x-10 gap-y-4">
            <div>
              <p className="text-2xs uppercase tracking-widest text-muted-foreground">Exposure</p>
              <AmountFlip value={12_00_00_000} className="text-3xl text-foreground" />
            </div>
            <div>
              <p className="text-2xs uppercase tracking-widest text-muted-foreground">Compact</p>
              <AmountFlip value={4_85_00_000} compact className="text-3xl text-foreground" />
            </div>
            <div>
              <p className="text-2xs uppercase tracking-widest text-muted-foreground">
                Open alerts
              </p>
              <CountUp value={1284} className="font-mono text-3xl font-semibold text-foreground" />
            </div>
          </div>
        </Section>

        <Section eyebrow="07 · primitives" title="SlaRing (RBI ≤30-day TAT)">
          <div className="flex flex-wrap items-center gap-8">
            <SlaRing dueTs={due(24)} now={now} size={56} />
            <SlaRing dueTs={due(5)} now={now} size={56} />
            <SlaRing dueTs={due(1)} now={now} size={56} />
            <SlaRing dueTs={due(-2)} now={now} size={56} />
          </div>
        </Section>

        <Section eyebrow="08 · primitives" title="Sparkline · PeerStrip">
          <div className="grid gap-8 sm:grid-cols-2">
            <div className="space-y-3 rounded-md border border-border bg-card p-4">
              <p className="text-2xs uppercase tracking-widest text-muted-foreground">
                30-day exposure trend
              </p>
              <Sparkline points={SPARK} width={220} height={44} area />
            </div>
            <div className="space-y-4 rounded-md border border-border bg-card p-4">
              <PeerStrip label="Access volume vs peers" value={182} peerMean={60} peerP95={120} />
              <PeerStrip label="Off-hours logins vs peers" value={44} peerMean={40} peerP95={90} />
            </div>
          </div>
        </Section>

        <Section eyebrow="09 · primitives" title="HashChainBlock (WORM audit chain)">
          <div className="max-w-md">
            <HashChainBlock
              index={42}
              action="PII unmask"
              hash="0x9f3a71c0be4d5521aa77e3b0c1f9d2e4c0a1b2c3"
              prevHash="0x71c0be4d5521aa77e3b0c1f9d2e4c0a1b2c3d4e5"
              ts="2026-06-30T14:22:07+05:30"
            />
            <HashChainBlock
              index={41}
              action="override approve"
              hash="0x71c0be4d5521aa77e3b0c1f9d2e4c0a1b2c3d4e5"
              prevHash="0xbe4d5521aa77e3b0c1f9d2e4c0a1b2c3d4e5f6a7"
              ts="2026-06-30T14:19:55+05:30"
              ok={false}
            />
            <HashChainBlock
              index={40}
              action="genesis"
              hash="0xbe4d5521aa77e3b0c1f9d2e4c0a1b2c3d4e5f6a7"
              ts="2026-06-30T14:00:00+05:30"
              connector={false}
            />
          </div>
        </Section>

        <Section eyebrow="10 · primitives" title="EventTicker (live replay tape)">
          <div className="h-64 max-w-md">
            <EventTicker items={ticks} live />
          </div>
        </Section>

        {/* ── Motion ─────────────────────────────────────────────── */}
        <Section eyebrow="11 · motion" title="Staggered reveal">
          <m.ul
            key={`stagger-${nonce}`}
            variants={staggerParent}
            initial="hidden"
            animate="show"
            className="grid grid-cols-2 gap-3 sm:grid-cols-4"
          >
            {['Detect', 'Explain', 'Contest', 'Decide'].map((s) => (
              <m.li
                key={s}
                variants={staggerItem}
                className="rounded-md border border-border bg-card px-4 py-6 text-center font-display text-lg text-foreground shadow-dossier"
              >
                {s}
              </m.li>
            ))}
          </m.ul>
        </Section>

        <Section eyebrow="12 · texture" title="PaperField (opt-in)">
          <div className="grid gap-4 sm:grid-cols-2">
            <PaperField
              grain
              className="flex h-32 items-center justify-center rounded-md border border-border"
            >
              <span className="text-sm text-muted-foreground">paper-grain</span>
            </PaperField>
            <PaperField
              grain={false}
              grid
              className="flex h-32 items-center justify-center rounded-md border border-border"
            >
              <span className="text-sm text-muted-foreground">blueprint grid</span>
            </PaperField>
          </div>
        </Section>

        <footer className="border-t border-border py-8 text-center font-mono text-3xs uppercase tracking-widest text-muted-foreground">
          docs/ui/UI_UPLIFT.md · alert-only · a human always decides
        </footer>
      </div>
    </RouteTransition>
  )
}

/* ── mock tape data ──────────────────────────────────────────────────────── */
const LEVELS: RiskLevel[] = ['low', 'low', 'medium', 'high', 'critical']
const VERBS = ['bulk export', 'after-hours login', 'limit override', 'vault access', 'wire release']

function pad(n: number): string {
  return n.toString().padStart(2, '0')
}
function makeTick(seq: number): TickerItem {
  const d = new Date()
  const level = LEVELS[Math.floor(Math.random() * LEVELS.length)]
  return {
    id: `evt-${d.getTime()}-${seq}`,
    ts: `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`,
    actor: `EMP-${Math.floor(Math.random() * 0xffff)
      .toString(16)
      .padStart(4, '0')}`,
    text: VERBS[Math.floor(Math.random() * VERBS.length)],
    level,
    amount: level === 'low' ? undefined : `₹${Math.floor(Math.random() * 90) + 10}L`,
  }
}
function seedTicks(): TickerItem[] {
  return Array.from({ length: 6 }, (_, i) => makeTick(i))
}
