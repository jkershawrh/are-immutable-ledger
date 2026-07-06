import { LedgerEntry } from '../api/ledgerApi'
import { useLedgerStore, sourceColor, sourceName } from '../store/ledgerStore'

export function DetailSidebar({ entry }: { entry: LedgerEntry }) {
  const selectEntry = useLedgerStore(s => s.selectEntry)
  const color = sourceColor(entry.source_id)

  return (
    <div style={{
      width: 320, borderLeft: '1px solid var(--border)', background: 'var(--surface-1)',
      overflowY: 'auto', padding: 16, flexShrink: 0,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <h3 style={{ fontSize: 14, fontWeight: 700 }}>Entry Detail</h3>
        <button onClick={() => selectEntry(null)} style={{
          background: 'transparent', border: 'none', color: 'var(--text-dim)',
          cursor: 'pointer', fontSize: 16,
        }}>×</button>
      </div>

      <Field label="Entry Type" value={entry.entry_type} color={color} />
      <Field label="Agent ID" value={entry.agent_id} />
      <Field label="Source" value={sourceName(entry.source_id)} color={color} />
      <Field label="Chain Position" value={String(entry.chain_position)} />
      <Field label="Correlation ID" value={entry.correlation_id || '—'} />

      <div style={{ margin: '12px 0', borderTop: '1px solid var(--border)' }} />

      <Field label="Entry Hash" value={entry.entry_hash} mono />
      <Field label="Previous Hash" value={entry.previous_hash} mono />

      {entry.writer_signature && (
        <>
          <div style={{ margin: '12px 0', borderTop: '1px solid var(--border)' }} />
          <div style={{ fontSize: 11, color: 'var(--purple)', fontWeight: 600, marginBottom: 8 }}>
            ✎ Signed
          </div>
          <Field label="Signer" value={entry.signer_key_reference || '—'} />
        </>
      )}

      {entry.content && (
        <>
          <div style={{ margin: '12px 0', borderTop: '1px solid var(--border)' }} />
          <div style={{ fontSize: 11, color: 'var(--text-dim)', fontWeight: 600, marginBottom: 8 }}>
            Content
          </div>
          <pre style={{
            fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)',
            background: 'var(--surface-2)', padding: 10, borderRadius: 6,
            overflow: 'auto', maxHeight: 200, whiteSpace: 'pre-wrap', wordBreak: 'break-all',
          }}>
            {typeof entry.content === 'object'
              ? JSON.stringify(entry.content, null, 2)
              : entry.content_raw}
          </pre>
        </>
      )}
    </div>
  )
}

function Field({ label, value, color, mono }: { label: string; value: string; color?: string; mono?: boolean }) {
  return (
    <div style={{ marginBottom: 8 }}>
      <div style={{ fontSize: 10, color: 'var(--text-disabled)', textTransform: 'uppercase', letterSpacing: 0.5 }}>
        {label}
      </div>
      <div style={{
        fontSize: mono ? 10 : 12, color: color || 'var(--text-secondary)',
        fontFamily: mono ? 'var(--font-mono)' : 'var(--font-text)',
        wordBreak: 'break-all',
      }}>
        {value}
      </div>
    </div>
  )
}
