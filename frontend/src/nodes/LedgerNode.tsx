import { Handle, Position, type NodeProps } from '@xyflow/react'

export interface LedgerNodeData {
  totalEntries: number
  chainCount: number
  crossSystem: number
  [key: string]: unknown
}

export function LedgerNode({ data }: NodeProps) {
  const d = data as unknown as LedgerNodeData
  return (
    <div style={{
      padding: '16px 24px',
      background: 'var(--surface-2)',
      border: '2px solid transparent',
      borderImage: 'linear-gradient(135deg, #3b82f6, #a78bfa) 1',
      borderRadius: 14,
      textAlign: 'center',
      minWidth: 180,
    }}>
      <div style={{
        fontSize: 16, fontWeight: 900, fontFamily: 'var(--font-display)',
        background: 'linear-gradient(135deg, #3b82f6, #a78bfa)',
        WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
      }}>
        Immutable Ledger
      </div>
      <div style={{ fontSize: 10, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', marginTop: 4 }}>
        {d.totalEntries} entries · {d.chainCount} chains
      </div>
      {d.crossSystem > 0 && (
        <div style={{ fontSize: 10, color: '#3b82f6', marginTop: 2 }}>
          {d.crossSystem} cross-system
        </div>
      )}
      <Handle type="target" position={Position.Left} style={{ background: '#3b82f6', width: 8, height: 8 }} />
      <Handle type="source" position={Position.Right} style={{ background: '#a78bfa', width: 8, height: 8 }} />
      <Handle type="target" position={Position.Top} id="top" style={{ background: '#3b82f6', width: 8, height: 8 }} />
      <Handle type="target" position={Position.Bottom} id="bottom" style={{ background: '#3b82f6', width: 8, height: 8 }} />
    </div>
  )
}
