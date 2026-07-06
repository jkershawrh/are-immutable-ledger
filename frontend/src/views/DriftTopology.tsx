import { useMemo } from 'react'
import { ReactFlow, Background, Controls, type Node, type Edge, MarkerType } from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { useLedgerStore } from '../store/ledgerStore'

export function DriftTopology() {
  const driftGaps = useLedgerStore(s => s.driftGaps)
  const entries = useLedgerStore(s => s.entries)

  const { nodes, edges } = useMemo(() => {
    const nodes: Node[] = []
    const edges: Edge[] = []

    if (driftGaps.length === 0) {
      nodes.push({
        id: 'no-gaps',
        type: 'default',
        position: { x: 200, y: 150 },
        data: { label: '✓ No authorization gaps detected' },
        style: {
          background: 'rgba(74, 222, 128, 0.08)', border: '1px solid rgba(74, 222, 128, 0.2)',
          color: '#4ade80', fontSize: 16, fontWeight: 700, padding: '20px 40px', borderRadius: 12,
        },
      })
      return { nodes, edges }
    }

    // Denied entries as red nodes
    let yOffset = 0
    for (const gap of driftGaps) {
      const denyNodeId = `deny-${gap.entry_id}`
      nodes.push({
        id: denyNodeId,
        type: 'default',
        position: { x: 100, y: yOffset },
        data: { label: `⛔ ${gap.detail}` },
        style: {
          background: 'rgba(249, 115, 22, 0.08)', border: '2px solid rgba(249, 115, 22, 0.4)',
          color: '#f97316', fontSize: 11, fontFamily: 'var(--font-mono)',
          padding: '10px 14px', borderRadius: 8, maxWidth: 250,
        },
      })

      // Missing scope eval as a ghost node
      const missingNodeId = `missing-${gap.entry_id}`
      nodes.push({
        id: missingNodeId,
        type: 'default',
        position: { x: 500, y: yOffset },
        data: { label: '? Missing scope evaluation' },
        style: {
          background: 'rgba(239, 68, 68, 0.05)', border: '2px dashed rgba(239, 68, 68, 0.3)',
          color: '#ef4444', fontSize: 11, fontFamily: 'var(--font-mono)',
          padding: '10px 14px', borderRadius: 8,
        },
      })

      // Gap edge
      edges.push({
        id: `gap-${gap.entry_id}`,
        source: denyNodeId,
        target: missingNodeId,
        style: { stroke: '#ef4444', strokeWidth: 2, strokeDasharray: '6 4' },
        animated: true,
        label: gap.correlation_id?.slice(0, 10) || 'no correlation',
        labelStyle: { fontSize: 9, fill: '#ef4444' },
        markerEnd: { type: MarkerType.ArrowClosed, color: '#ef4444' },
      })

      // Agent info below the deny node
      nodes.push({
        id: `info-${gap.entry_id}`,
        type: 'default',
        position: { x: 100, y: yOffset + 55 },
        data: { label: `agent: ${gap.agent_id} · source: ${gap.source_id}` },
        style: {
          background: 'transparent', border: 'none',
          color: 'var(--text-disabled)', fontSize: 9, fontFamily: 'var(--font-mono)',
          padding: 0,
        },
        selectable: false, draggable: false,
      })

      yOffset += 120
    }

    return { nodes, edges }
  }, [driftGaps])

  return (
    <div style={{ width: '100%', height: '100%' }}>
      <ReactFlow nodes={nodes} edges={edges} fitView
        proOptions={{ hideAttribution: true }} style={{ background: 'var(--bg-dark)' }}>
        <Background color="var(--border)" gap={20} size={1} />
        <Controls position="bottom-left" />
      </ReactFlow>
    </div>
  )
}
