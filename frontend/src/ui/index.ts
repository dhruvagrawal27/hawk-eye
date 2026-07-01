/**
 * `@/ui` — the "Daylight Forensics" design-system barrel (Agent A). One import surface for the
 * signature primitives, the motion foundation, and the shared risk/SLA/format helpers the kit is built
 * on. Feature screens (Agent B) consume from here; see docs/ui/UI_UPLIFT.md for the contract.
 */

// Signature primitives
export { RiskGauge, type RiskGaugeProps, type RiskGaugeSize } from './RiskGauge'
export { AmountFlip, CountUp, type AmountFlipProps, type CountUpProps } from './AmountFlip'
export { SlaRing, type SlaRingProps } from './SlaRing'
export { Sparkline, type SparklineProps } from './Sparkline'
export { PeerStrip, type PeerStripProps } from './PeerStrip'
export { HashChainBlock, type HashChainBlockProps } from './HashChainBlock'
export { EventTicker, type TickerItem, type EventTickerProps } from './EventTicker'
export { PaperField, type PaperFieldProps } from './PaperField'

// Motion foundation
export {
  MotionProvider,
  RouteTransition,
  useReducedMotionSafe,
  useAutoAnimateList,
  useMagnetic,
  pageVariants,
  staggerParent,
  staggerItem,
  spotlight,
  dossierSpring,
  m,
  AnimatePresence,
  LazyMotion,
  domAnimation,
} from './motion'

// Shared helpers the kit is built on (re-exported so B has one import surface)
export {
  riskColor,
  riskLevel,
  riskLevelFromScore,
  riskRowStyle,
  RISK_VAR,
  RISK_TEXT,
  type RiskLevel,
} from '@/lib/risk'
export {
  severityForScore,
  formatINR,
  formatINRCompact,
  formatNumber,
  slaInfo,
  type SlaState,
  type SlaInfo,
} from '@/lib/format'
