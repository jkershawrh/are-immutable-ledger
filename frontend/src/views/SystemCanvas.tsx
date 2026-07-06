import { useCallback, useEffect, useMemo } from 'react'
import { ReactFlow, Background, Controls, MiniMap, type Node, type Edge, MarkerType } from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { useLedgerStore, sourceColor } from '../store/ledgerStore'
import { ServiceNode } from '../nodes/ServiceNode'
import { LedgerNode } from '../nodes/LedgerNode'

const nodeTypes = { service: ServiceNode, ledger: LedgerNode }

export function SystemCanvas() {
  const summary = useLedgerStore(s => s.summary)
  const chains = useLedgerStore(s => s.chains)
  const selectSource = useLedgerStore(s => s.selectSource)

  const sourceCounts = useMemo(() => {
    const counts: Record<string, number> = {}
    for (const c of chains) {
      const src = c.source
      counts[src] = (counts[src] || 0) + c.count
    }
    return counts
  }, [chains])

  const nodes: Node[] = useMemo(() => [
    { id: 'openshell', type: 'service', position: { x: 50, y: 50 },
      data: { label: 'OpenShell', subtitle: 'OCSF Events', color: sourceColor('openshell'), entryCount: sourceCounts['openshell'] || 0 } },
    { id: 'kagenti', type: 'service', position: { x: 50, y: 220 },
      data: { label: 'Kagenti', subtitle: 'OTEL Spans', color: sourceColor('kagenti'), entryCount: sourceCounts['kagenti'] || 0 } },
    { id: 'governance', type: 'service', position: { x: 50, y: 390 },
      data: { label: 'Governance', subtitle: 'Authority Decisions', color: sourceColor('gov'), entryCount: sourceCounts['governance'] || 0 } },
    { id: 'ledger', type: 'ledger', position: { x: 400, y: 200 },
      data: { totalEntries: summary?.total_entries || 0, chainCount: summary?.chain_types || 0, crossSystem: summary?.cross_system_correlations || 0 } },
    { id: 'explorer', type: 'service', position: { x: 700, y: 220 },
      data: { label: 'Proof Explorer', subtitle: 'verify · query · drift', color: '#7a7f94' } },
  ], [summary, sourceCounts])

  const edges: Edge[] = useMemo(() => [
    { id: 'os-l', source: 'openshell', target: 'ledger', animated: true, style: { stroke: sourceColor('openshell') },
      markerEnd: { type: MarkerType.ArrowClosed, color: sourceColor('openshell') }, label: 'adapter' },
    { id: 'kg-l', source: 'kagenti', target: 'ledger', animated: true, style: { stroke: sourceColor('kagenti') },
      markerEnd: { type: MarkerType.ArrowClosed, color: sourceColor('kagenti') }, label: 'adapter' },
    { id: 'gv-l', source: 'governance', target: 'ledger', animated: true, style: { stroke: sourceColor('gov') },
      markerEnd: { type: MarkerType.ArrowClosed, color: sourceColor('gov') }, label: 'adapter' },
    { id: 'l-ex', source: 'ledger', target: 'explorer', style: { stroke: '#7a7f94', strokeDasharray: '4 4' },
      markerEnd: { type: MarkerType.ArrowClosed, color: '#7a7f94' } },
  ], [])

  const onNodeClick = useCallback((_: React.MouseEvent, node: Node) => {
    if (node.id !== 'ledger' && node.id !== 'explorer') {
      selectSource(node.id)
    }
  }, [selectSource])

  return (
    <div style={{ width: '100%', height: '100%' }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodeClick={onNodeClick}
        fitView
        proOptions={{ hideAttribution: true }}
        style={{ background: 'var(--bg-dark)' }}
      >
        <Background color="var(--border)" gap={20} size={1} />
        <Controls position="bottom-left" style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: 8 }} />
        <MiniMap style={{ background: 'var(--surface-1)', border: '1px solid var(--border)' }} nodeColor={(n) => {
          const d = n.data as Record<string, unknown>
          return (d.color as string) || '#7a7f94'
        }} />
      </ReactFlow>
    </div>
  )
}
