import { Handle, Position, type NodeProps } from '@xyflow/react'
import { useLedgerStore, sourceColor } from '../store/ledgerStore'

export interface EntryNodeData {
  entryId: string
  entryHash: string
  entryType: string
  chainPosition: number
  sourceId: string
  agentId: string
  writtenTs: number
  correlationId: string
  [key: string]: unknown
}

export function EntryNode({ data, selected }: NodeProps) {
  const d = data as unknown as EntryNodeData
  const color = sourceColor(d.sourceId)
  const selectEntry = useLedgerStore(s => s.selectEntry)

  return (
    <div
      onClick={() => selectEntry(d.entryId)}
      style={{
        padding: '8px 12px',
        background: selected ? 'var(--surface-3)' : 'var(--surface-2)',
        border: `1.5px solid ${selected ? color : 'var(--border)'}`,
        borderRadius: 8,
        cursor: 'pointer',
        minWidth: 120,
        transition: 'border-color 0.2s',
      }}
    >
      <div style={{ fontSize: 10, color, fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
        #{d.chainPosition}
      </div>
      <div style={{ fontSize: 9, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', marginTop: 2 }}>
        {d.entryHash.slice(0, 12)}...
      </div>
      {d.correlationId && (
        <div style={{ fontSize: 8, color: 'var(--text-disabled)', fontFamily: 'var(--font-mono)', marginTop: 2 }}>
          ⟷ {d.correlationId.slice(0, 10)}
        </div>
      )}
      <Handle type="target" position={Position.Left} style={{ background: color, width: 6, height: 6 }} />
      <Handle type="source" position={Position.Right} style={{ background: color, width: 6, height: 6 }} />
    </div>
  )
}
