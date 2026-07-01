/**
 * Plain-language definitions for the insider-risk index (M2.1) — sub-scores, drivers, and the
 * composition formula. Used for hover tooltips + the "how this score was computed" breakdown so an
 * investigator can understand every number. Kept in sync with ml/pipelines/insider_risk_index.py.
 */

/** The three sub-scores: what each measures + which signals compose it. */
export const GROUP_DEFINITIONS: Record<
  'hr_score' | 'access_score' | 'anomaly_score',
  { label: string; weight: number; tooltip: string }
> = {
  hr_score: {
    label: 'HR posture',
    weight: 0.3,
    tooltip:
      'Employee-lifecycle stability. Blends: no-leave streak (never taking leave, a classic embezzlement tell), a recently-filed grievance, a recent role change, and leaver/notice-period status. Higher = more HR-driven risk.',
  },
  access_score: {
    label: 'Access posture',
    weight: 0.35,
    tooltip:
      'Entitlement & account risk. Blends: entitlement-change velocity, standing (granted-but-unexercised) privileges, and dormant-account reactivation. Higher = more over-privileging / access risk.',
  },
  anomaly_score: {
    label: 'Recent anomaly',
    weight: 0.35,
    tooltip:
      'Recent abnormal behaviour. Blends: off-hours activity and the number of alerts this user triggered in the last 30 days. Higher = more recent anomalous activity.',
  },
}

/** Per-driver plain-language meaning (the "top drivers" chips). */
export const DRIVER_TOOLTIPS: Record<string, string> = {
  no_leave_taken_streak:
    'Days worked with no leave taken. A never-takes-leave pattern is a classic fraud tell (prevents hand-off that would expose manipulation).',
  grievance_recency:
    'How recently the staffer filed an HR grievance (decays over ~180 days). A fresh grievance is a disgruntlement signal.',
  role_change_recency:
    'How recently the staffer changed role (decays over ~90 days). New access + unfamiliar controls raise risk.',
  leaver_or_notice:
    'The staffer is a leaver or in their notice period — the highest-risk window for data theft / sabotage.',
  entitlement_change_velocity:
    'Rate of permission grants/changes. Rapid entitlement churn indicates privilege creep or escalation.',
  standing_privilege:
    'Entitlements held but not exercised (least-privilege gap). Unused standing access is an evasion vector.',
  dormant_reactivation:
    'A dormant/never-used account was reactivated — a takeover / resurrection signal.',
  offhours_score:
    'Share of activity outside bank hours (IST Mon–Fri 08:00–20:00). Off-hours work evades supervision.',
  recent_alerts_30d:
    'Count of alerts this user triggered in the last 30 days — recent detected anomalies.',
}

export function driverTooltip(driver: string): string | undefined {
  return DRIVER_TOOLTIPS[driver]
}
