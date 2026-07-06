import { Handle, Position, type NodeProps } from '@xyflow/react'

export interface ServiceNodeData {
  label: string
  subtitle: string
  color: string
  entryCount?: number
  status?: string
  [key: string]: unknown
}

export function ServiceNode({ data }: NodeProps) {
  const d = data as unknown as ServiceNodeData
  return (
    <div style={{
      padding: '14px 20px',
      background: 'var(--surface-2)',
      border: `2px solid ${d.color}`,
      borderRadius: 12,
      textAlign: 'center',
      minWidth: 160,
    }}>
      <div style={{ fontSize: 14, fontWeight: 700, fontFamily: 'var(--font-display)', color: 'var(--text-primary)' }}>
        {d.label}
      </div>
      <div style={{ fontSize: 10, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', marginTop: 4 }}>
        {d.subtitle}
      </div>
      {d.entryCount !== undefined && (
        <div style={{ fontSize: 11, color: d.color, fontWeight: 600, marginTop: 6 }}>
          {d.entryCount} entries
        </div>
      )}
      {d.status && (
        <div style={{ fontSize: 9, color: d.color, fontFamily: 'var(--font-mono)', marginTop: 2 }}>
          {d.status}
        </div>
      )}
      <Handle type="target" position={Position.Left} style={{ background: d.color, width: 8, height: 8 }} />
      <Handle type="source" position={Position.Right} style={{ background: d.color, width: 8, height: 8 }} />
    </div>
  )
}
