/**
 * Phase 3 — Entity-360 deep dive. The 7×24 activity heatmap surfaces off-hours concentration (a
 * first-order insider signal) from the entity's own timeline.
 */
import { describe, expect, it } from 'vitest'
import { render } from '@testing-library/react'
import { ActivityHeatmap, bucketIsOffHours } from '@/components/ActivityHeatmap'

describe('bucketIsOffHours — IST bank-hours rule', () => {
  it('flags weekends at any hour', () => {
    expect(bucketIsOffHours(5, 10)).toBe(true) // Sat 10:00
    expect(bucketIsOffHours(6, 14)).toBe(true) // Sun 14:00
  })
  it('flags weekday nights (before 08:00, from 20:00)', () => {
    expect(bucketIsOffHours(0, 2)).toBe(true) // Mon 02:00
    expect(bucketIsOffHours(0, 7)).toBe(true) // Mon 07:00
    expect(bucketIsOffHours(0, 20)).toBe(true) // Mon 20:00
  })
  it('treats weekday bank hours as on-hours', () => {
    expect(bucketIsOffHours(0, 8)).toBe(false) // Mon 08:00
    expect(bucketIsOffHours(2, 14)).toBe(false) // Wed 14:00
    expect(bucketIsOffHours(4, 19)).toBe(false) // Fri 19:00
  })
})

describe('ActivityHeatmap render', () => {
  it('shows the total event count and an off-hours share', () => {
    const { getByText } = render(
      <ActivityHeatmap
        points={[
          { ts: '2026-06-30T02:14:07Z', offHours: true },
          { ts: '2026-06-30T05:30:00Z', offHours: false },
          { ts: '2026-06-30T09:00:00Z', offHours: true },
        ]}
      />,
    )
    getByText('3 events')
    getByText(/% off-hours/)
    getByText('Activity heatmap · IST')
  })
})
