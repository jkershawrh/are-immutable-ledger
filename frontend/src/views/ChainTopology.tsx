import { useMemo } from 'react'
import { ReactFlow, Background, Controls, MiniMap, type Node, type Edge, MarkerType } from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { useLedgerStore, sourceColor } from '../store/ledgerStore'
import { EntryNode } from '../nodes/EntryNode'

const nodeTypes = { entry: EntryNode }

export function ChainTopology() {
  const chains = useLedgerStore(s => s.chains)
  const entries = useLedgerStore(s => s.entries)

  const { nodes, edges } = useMemo(() => {
    const nodes: Node[] = []
    const edges: Edge[] = []
    const correlationEntries: Record<string, string[]> = {}

    let yOffset = 0
    for (const chain of chains) {
      const color = sourceColor(chain.source)

      // Chain label node
      nodes.push({
        id: `label-${chain.entry_type}`,
        type: 'default',
        position: { x: -20, y: yOffset + 15 },
        data: { label: chain.entry_type },
        style: {
          background: 'transparent', border: 'none', color,
          fontSize: 10, fontFamily: 'var(--font-mono)', fontWeight: 600,
          width: 'auto', padding: '2px 6px',
        },
        selectable: false, draggable: false,
      })

      // Entry nodes in this chain
      const sorted = [...chain.entries].sort((a, b) => a.chain_position - b.chain_position)
      for (let i = 0; i < Math.min(sorted.length, 20); i++) {
        const entry = sorted[i]
        const nodeId = `entry-${entry.entry_id}`
        nodes.push({
          id: nodeId,
          type: 'entry',
          position: { x: 180 + i * 150, y: yOffset },
          data: {
            entryId: entry.entry_id,
            entryHash: entry.entry_hash,
            entryType: entry.entry_type,
            chainPosition: entry.chain_position,
            sourceId: entry.source_id,
            agentId: entry.agent_id,
            writtenTs: entry.written_ts,
            correlationId: entry.correlation_id || '',
          },
        })

        // Chain edge (hash link)
        if (i > 0) {
          edges.push({
            id: `chain-${entry.entry_id}`,
            source: `entry-${sorted[i - 1].entry_id}`,
            target: nodeId,
            style: { stroke: color, strokeWidth: 1.5 },
            markerEnd: { type: MarkerType.ArrowClosed, color, width: 12, height: 12 },
          })
        }

        // Track correlations
        if (entry.correlation_id) {
          if (!correlationEntries[entry.correlation_id]) correlationEntries[entry.correlation_id] = []
          correlationEntries[entry.correlation_id].push(nodeId)
        }
      }

      yOffset += 80
    }

    // Correlation edges (cross-chain)
    for (const [corrId, nodeIds] of Object.entries(correlationEntries)) {
      if (nodeIds.length < 2) continue
      for (let i = 1; i < nodeIds.length; i++) {
        edges.push({
          id: `corr-${corrId}-${i}`,
          source: nodeIds[0],
          target: nodeIds[i],
          style: { stroke: '#3b82f6', strokeWidth: 1, strokeDasharray: '4 4' },
          animated: true,
          label: corrId.slice(0, 8),
          labelStyle: { fontSize: 8, fill: '#3b82f6' },
        })
      }
    }

    return { nodes, edges }
  }, [chains])

  return (
    <div style={{ width: '100%', height: '100%' }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
        proOptions={{ hideAttribution: true }}
        style={{ background: 'var(--bg-dark)' }}
      >
        <Background color="var(--border)" gap={20} size={1} />
        <Controls position="bottom-left" />
        <MiniMap style={{ background: 'var(--surface-1)' }} />
      </ReactFlow>
    </div>
  )
}
