'use client';

import { Background, Controls, MarkerType, Position, ReactFlow, type Edge, type Node } from '@xyflow/react';
import '@xyflow/react/dist/style.css';

const roles = [
  { id: 'alice', label: 'Alice', sub: 'Delegates authority', x: 0, y: 95, color: '#a56eff' },
  { id: 'agent', label: 'agent-7', sub: '$100 mandate', x: 190, y: 95, color: '#4589ff' },
  { id: 'praxis', label: 'Praxis', sub: 'Gateway · target port', x: 380, y: 95, color: '#ee0000' },
  { id: 'cpex', label: 'CPEX / PPE', sub: 'Canonical seam today', x: 570, y: 95, color: '#0f62fe' },
  { id: 'ocsf', label: 'OCSF evidence', sub: 'Signed record', x: 760, y: 95, color: '#33b1ff' },
  { id: 'ledger', label: 'Immutable ledger', sub: 'Durable proof', x: 950, y: 95, color: '#42be65' },
  { id: 'verify', label: 'Offline verifier', sub: 'Independent trust', x: 1140, y: 95, color: '#f1c21b' },
];

const links = [['alice','agent'],['agent','praxis'],['praxis','cpex'],['cpex','ocsf'],['ocsf','ledger'],['ledger','verify']];

export function ProofFlow({ activeIndex, perspective = 'business' }: { activeIndex: number; perspective?: 'business' | 'technical' }) {
  const activeByStep = perspective === 'technical'
    ? ['agent','cpex','cpex','cpex','ocsf','ocsf','cpex','verify']
    : ['agent','praxis','cpex','cpex','cpex','ocsf','ledger','verify'];
  const active = activeByStep[Math.min(activeIndex, activeByStep.length - 1)];
  const nodes: Node[] = roles.map(role => ({
    id: role.id,
    position: { x: role.x, y: role.y },
    draggable: false,
    sourcePosition: Position.Right,
    targetPosition: Position.Left,
    data: { label: <div className="flow-node"><span className="flow-pulse" style={{ background: role.color }} /><strong>{role.label}</strong><small>{role.sub}</small></div> },
    className: role.id === active ? 'flow-card flow-card-active' : 'flow-card',
    style: { borderColor: role.id === active ? role.color : '#3b4552' },
  }));
  const edges: Edge[] = links.map(([source,target], index) => ({
    id: `${source}-${target}`,
    source,
    target,
    type: 'smoothstep',
    pathOptions: { borderRadius: 18, offset: 26 },
    animated: index <= Math.min(activeIndex, links.length - 1),
    style: { stroke: index <= activeIndex ? '#78a9ff' : '#3b4552', strokeWidth: 2 },
    markerEnd: { type: MarkerType.ArrowClosed, color: index <= activeIndex ? '#78a9ff' : '#3b4552' },
  }));

  return (
    <div className="flow-wrap" aria-label="Verdict-to-proof architecture">
      <ReactFlow nodes={nodes} edges={edges} fitView fitViewOptions={{ padding: .16 }} nodesDraggable={false} nodesConnectable={false} panOnDrag zoomOnScroll minZoom={.6} maxZoom={1.25} proOptions={{ hideAttribution: true }}>
        <Background color="#26303a" gap={22} size={1} />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}
