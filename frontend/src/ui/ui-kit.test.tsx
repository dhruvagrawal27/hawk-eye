import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import {
  AmountFlip,
  CountUp,
  RiskGauge,
  SlaRing,
  Sparkline,
  PeerStrip,
  HashChainBlock,
  EventTicker,
  useReducedMotionSafe,
  type TickerItem,
} from '@/ui'
import { renderHook } from '@testing-library/react'
import { contrastRatio, hslTripleToRgb, wcagRating } from './gallery/contrast'

/**
 * Design-system kit tests (Agent A). The signature primitives always expose their FINAL value in the
 * DOM (via text or aria-label), so this suite is deterministic and doubles as the reduced-motion floor:
 * a user who never sees an animation still gets every number.
 */

afterEach(cleanup)

describe('AmountFlip / CountUp — numeric roll-ups', () => {
  it('renders the final ₹ value instantly with durationMs=0 (Indian grouping)', () => {
    render(<AmountFlip value={12_00_00_000} durationMs={0} />)
    // Assert on the digit grouping, not the ₹ glyph (ICU currency spacing varies).
    expect(screen.getByLabelText(/12,00,00,000/)).toBeInTheDocument()
  })

  it('supports the compact crore form', () => {
    render(<AmountFlip value={4_85_00_000} compact durationMs={0} />)
    expect(screen.getByText(/4\.85 Cr/)).toBeInTheDocument()
  })

  it('renders a plain grouped count', () => {
    render(<AmountFlip value={1284} kind="plain" durationMs={0} />)
    expect(screen.getByText('1,284')).toBeInTheDocument()
  })

  it('CountUp shows the final integer and exposes it to AT', () => {
    render(<CountUp value={87} durationMs={0} />)
    expect(screen.getByLabelText('87')).toHaveTextContent('87')
  })
})

describe('RiskGauge', () => {
  it('is an img with an informative label (score, band, confidence)', () => {
    render(<RiskGauge score={92} confidence={0.86} label="risk" animateNumber={false} />)
    const img = screen.getByRole('img')
    expect(img).toHaveAttribute('aria-label', expect.stringContaining('92 of 100'))
    expect(img.getAttribute('aria-label')).toMatch(/confidence 86%/)
    expect(img.getAttribute('aria-label')).toMatch(/critical band/)
  })

  it('normalises the ramp for a custom max', () => {
    render(<RiskGauge score={2} max={10} animateNumber={false} />)
    // 2/10 = 20% → low band
    expect(screen.getByRole('img').getAttribute('aria-label')).toMatch(/low band/)
  })
})

describe('SlaRing — RBI ≤30-day TAT', () => {
  const now = new Date('2026-06-30T00:00:00Z')

  it('is ok well inside the window', () => {
    const { container } = render(<SlaRing dueTs="2026-07-24T00:00:00Z" now={now} />)
    expect(container.querySelector('[data-sla-state]')).toHaveAttribute('data-sla-state', 'ok')
  })

  it('is urgent within 72h', () => {
    const { container } = render(<SlaRing dueTs="2026-07-01T00:00:00Z" now={now} />)
    expect(container.querySelector('[data-sla-state]')).toHaveAttribute('data-sla-state', 'urgent')
  })

  it('is breached past due', () => {
    const { container } = render(<SlaRing dueTs="2026-06-28T00:00:00Z" now={now} />)
    expect(container.querySelector('[data-sla-state]')).toHaveAttribute(
      'data-sla-state',
      'breached',
    )
    expect(screen.getByText(/Breached/)).toBeInTheDocument()
  })
})

describe('Sparkline', () => {
  it('draws a path for a series and an end marker', () => {
    const { container } = render(<Sparkline points={[1, 3, 2, 5, 4]} />)
    expect(container.querySelector('path')).toBeInTheDocument()
    expect(container.querySelector('circle')).toBeInTheDocument()
  })

  it('does not crash on empty input', () => {
    const { container } = render(<Sparkline points={[]} />)
    expect(container.querySelector('svg')).toBeInTheDocument()
    expect(container.querySelector('path')).toBeNull()
  })
})

describe('PeerStrip — peer-relative deviation', () => {
  it('labels a value beyond p95 as an outlier', () => {
    render(<PeerStrip label="Access" value={182} peerMean={60} peerP95={120} />)
    expect(screen.getByText('outlier')).toBeInTheDocument()
    expect(screen.getByRole('img').getAttribute('aria-label')).toMatch(/outlier/)
  })

  it('labels a value inside the cohort', () => {
    render(<PeerStrip label="Access" value={30} peerMean={60} peerP95={120} />)
    expect(screen.getByText('in cohort')).toBeInTheDocument()
  })
})

describe('HashChainBlock — WORM audit chain', () => {
  it('shows the index, seal, and a truncated hash with the full value in title', () => {
    render(
      <HashChainBlock
        index={42}
        action="PII unmask"
        hash="0x9f3a71c0be4d5521aa77e3b0c1f9d2e4c0a1b2c3"
        prevHash="0x71c0be4d5521aa77e3b0c1f9d2e4c0a1b2c3d4e5"
      />,
    )
    expect(screen.getByText('#42')).toBeInTheDocument()
    expect(screen.getByText('sealed')).toBeInTheDocument()
    const hashEl = screen.getByTitle('0x9f3a71c0be4d5521aa77e3b0c1f9d2e4c0a1b2c3')
    expect(hashEl.textContent).toMatch(/…/)
  })

  it('marks a broken link', () => {
    render(<HashChainBlock index={1} hash="0xabc123def456abc123def456" ok={false} />)
    expect(screen.getByText('broken')).toBeInTheDocument()
  })
})

describe('EventTicker', () => {
  const items: TickerItem[] = [
    {
      id: 'a',
      ts: '12:00:01',
      actor: 'EMP-aa01',
      text: 'bulk export',
      level: 'high',
      amount: '₹40L',
    },
    { id: 'b', ts: '12:00:00', actor: 'EMP-bb02', text: 'after-hours login', level: 'low' },
  ]

  it('renders rows and the live indicator', () => {
    render(<EventTicker items={items} live />)
    expect(screen.getByText('bulk export')).toBeInTheDocument()
    expect(screen.getByText('EMP-aa01')).toBeInTheDocument()
    expect(screen.getByText('live')).toBeInTheDocument()
  })

  it('shows an empty state', () => {
    render(<EventTicker items={[]} />)
    expect(screen.getByText(/No events yet/)).toBeInTheDocument()
  })
})

describe('contrast helpers (gallery token audit)', () => {
  it('converts greyscale HSL correctly', () => {
    expect(hslTripleToRgb('0 0% 100%')).toEqual([255, 255, 255])
    expect(hslTripleToRgb('0 0% 0%')).toEqual([0, 0, 0])
  })

  it('black-on-white is the maximal 21:1 ratio', () => {
    expect(contrastRatio('0 0% 0%', '0 0% 100%')).toBeCloseTo(21, 0)
  })

  it('rates ratios per WCAG', () => {
    expect(wcagRating(21)).toBe('AAA')
    expect(wcagRating(4.6)).toBe('AA')
    expect(wcagRating(3.2)).toBe('AA Large')
    expect(wcagRating(2)).toBe('Fail')
  })

  it('warm ink on porcelain clears AA (the app default pairing)', () => {
    // The live tokens: --foreground on --background.
    expect(contrastRatio('30 14% 12%', '40 30% 97%')).toBeGreaterThan(4.5)
  })
})

describe('reduced-motion contract', () => {
  const realMatchMedia = window.matchMedia
  afterEach(() => {
    window.matchMedia = realMatchMedia
    vi.restoreAllMocks()
  })

  function forceReducedMotion() {
    window.matchMedia = vi.fn().mockImplementation((query: string) => ({
      matches: /prefers-reduced-motion:\s*reduce/.test(query),
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })) as unknown as typeof window.matchMedia
  }

  it('useReducedMotionSafe reflects the OS preference', () => {
    forceReducedMotion()
    const { result } = renderHook(() => useReducedMotionSafe())
    expect(result.current).toBe(true)
  })

  it('AmountFlip renders the final value instantly under reduced motion', () => {
    forceReducedMotion()
    render(<AmountFlip value={48_00_000} />)
    expect(screen.getByLabelText(/48,00,000/)).toBeInTheDocument()
  })
})
