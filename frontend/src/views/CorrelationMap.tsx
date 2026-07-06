import { useMemo } from 'react'
import { ReactFlow, Background, Controls, MiniMap, type Node, type Edge } from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { useLedgerStore, sourceColor } from '../store/ledgerStore'
import { EntryNode } from '../nodes/EntryNode'

const nodeTypes = { entry: EntryNode }

export function CorrelationMap() {
  const entries = useLedgerStore(s => s.entries)

  const { nodes, edges } = useMemo(() => {
    const nodes: Node[] = []
    const edges: Edge[] = []

    // Group entries by correlation_id
    const byCorr: Record<string, typeof entries> = {}
    for (const e of entries) {
      if (!e.correlation_id || e.entry_type.startsWith('test.')) continue
      if (!byCorr[e.correlation_id]) byCorr[e.correlation_id] = []
      byCorr[e.correlation_id].push(e)
    }

    // Only show correlations with 2+ entries
    const multiCorr = Object.entries(byCorr).filter(([, es]) => es.length >= 2)

    let yOffset = 0
    for (const [corrId, corrEntries] of multiCorr) {
      const sources = new Set(corrEntries.map(e => e.source_id))
      const isMultiSource = sources.size > 1

      // Lane label
      nodes.push({
        id: `lane-${corrId}`,
        type: 'default',
        position: { x: -20, y: yOffset + 10 },
        data: { label: `${corrId.slice(0, 16)}${corrId.length > 16 ? '...' : ''}` },
        style: {
          background: 'transparent', border: 'none',
          color: isMultiSource ? '#3b82f6' : 'var(--text-disabled)',
          fontSize: 9, fontFamily: 'var(--font-mono)', fontWeight: isMultiSource ? 700 : 400,
          width: 'auto', padding: '2px 6px',
        },
        selectable: false, draggable: false,
      })

      // Entry nodes in this lane
      const sorted = [...corrEntries].sort((a, b) => a.written_ts - b.written_ts)
      for (let i = 0; i < sorted.length; i++) {
        const e = sorted[i]
        const nodeId = `corr-${corrId}-${e.entry_id}`
        nodes.push({
          id: nodeId,
          type: 'entry',
          position: { x: 200 + i * 180, y: yOffset },
          data: {
            entryId: e.entry_id, entryHash: e.entry_hash, entryType: e.entry_type,
            chainPosition: e.chain_position, sourceId: e.source_id,
            agentId: e.agent_id, writtenTs: e.written_ts, correlationId: e.correlation_id || '',
          },
        })

        if (i > 0) {
          const prevSrc = sorted[i - 1].source_id
          const curSrc = e.source_id
          const crossSystem = prevSrc !== curSrc
          edges.push({
            id: `corrlink-${corrId}-${i}`,
            source: `corr-${corrId}-${sorted[i - 1].entry_id}`,
            target: nodeId,
            style: {
              stroke: crossSystem ? '#3b82f6' : sourceColor(curSrc),
              strokeWidth: crossSystem ? 2 : 1,
              strokeDasharray: crossSystem ? undefined : '4 4',
            },
            animated: crossSystem,
          })
        }
      }

      yOffset += 80
    }

    return { nodes, edges }
  }, [entries])

  if (nodes.length === 0) {
    return <div style={{ padding: 40, color: 'var(--text-dim)', textAlign: 'center' }}>No cross-system correlations found</div>
  }

  return (
    <div style={{ width: '100%', height: '100%' }}>
      <ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} fitView
        proOptions={{ hideAttribution: true }} style={{ background: 'var(--bg-dark)' }}>
        <Background color="var(--border)" gap={20} size={1} />
        <Controls position="bottom-left" />
        <MiniMap style={{ background: 'var(--surface-1)' }} />
      </ReactFlow>
    </div>
  )
}
