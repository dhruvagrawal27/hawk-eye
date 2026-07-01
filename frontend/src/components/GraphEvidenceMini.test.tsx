/**
 * Deferred polish — inline L5 mini-graph. The graph evidence must be *drawn* (SVG nodes + edges),
 * not only described in text, so an investigator sees the ring shape at a glance.
 */
import { describe, expect, it } from 'vitest'
import { render } from '@testing-library/react'
import { GraphEvidenceMini } from '@/components/GraphEvidenceMini'
import type { GraphEvidence } from '@/lib/types'

const graph: GraphEvidence = {
  ring_id: 'RNG-12',
  summary: 'isolated maker-checker pair',
  explainer_model: 'GNNExplainer',
  nodes: [
    { id: 'EMP-7f3a', label: 'EMP-7f3a', type: 'employee', importance: 1 },
    { id: 'EMP-1a09', label: 'EMP-1a09', type: 'employee', importance: 0.86 },
    { id: 'BEN-9b1c', label: 'BEN-9b1c', type: 'beneficiary', importance: 0.71 },
  ],
  edges: [
    { source: 'EMP-7f3a', target: 'EMP-1a09', type: 'maker_checker', importance: 0.93 },
    { source: 'EMP-7f3a', target: 'BEN-9b1c', type: 'beneficiary', importance: 0.64 },
  ],
}

describe('GraphEvidenceMini', () => {
  it('draws a node circle per node and a line per edge', () => {
    const { container, getByText } = render(<GraphEvidenceMini graph={graph} />)
    // one filled circle per node (the centre also has a ring outline, so circles >= nodes)
    expect(container.querySelectorAll('circle').length).toBeGreaterThanOrEqual(3)
    // one line per edge
    expect(container.querySelectorAll('line').length).toBe(2)
    // node labels are rendered
    getByText('EMP-7f3a')
    getByText('BEN-9b1c')
  })

  it('renders nothing for a degenerate (single-node) subgraph', () => {
    const { container } = render(
      <GraphEvidenceMini graph={{ ...graph, nodes: graph.nodes.slice(0, 1), edges: [] }} />,
    )
    expect(container.querySelector('svg')).toBeNull()
  })
})
