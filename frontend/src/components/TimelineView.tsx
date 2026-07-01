import { motion } from 'motion/react'
import { useFetch } from '../hooks/useLedger'
import { api, LedgerEntry } from '../api/ledgerApi'
import { SourceBadge, sourceColor } from './SourceBadge'

function formatTime(ts: number): string {
  const d = new Date(ts)
  return d.toLocaleTimeString('en-US', { hour12: false }) + '.' + String(ts % 1000).padStart(3, '0')
}

function entryDetail(entry: LedgerEntry): string {
  if (!entry.content) return ''
  const c = entry.content
  if (c.tool && typeof c.tool === 'object') return `tool=${(c.tool as Record<string,string>).name || ''}`
  if (typeof c['tool.name'] === 'string') return `tool=${c['tool.name']}`
  if (typeof c.action === 'string') return c.action as string
  if (typeof c.effect === 'string') return `${c['action_class'] || ''} → ${c.effect}`
  if (typeof c.message === 'string') return (c.message as string).slice(0, 60)
  if (typeof c.task === 'string') return c.task as string
  return ''
}

export function TimelineView() {
  const { data, loading } = useFetch(() => api.timeline(), [])

  if (loading) return <div style={{ padding: 32, color: 'var(--text-dim)' }}>Loading timeline...</div>
  if (!data) return null

  const entries = data.entries.filter(e => !e.entry_type.startsWith('test.'))
  const correlations = data.correlations

  const multiSourceCorr = Object.entries(correlations).filter(([, ids]) => {
    const sources = new Set(ids.map(id => entries.find(e => e.entry_id === id)?.source_id || ''))
    return sources.size > 1
  })

  return (
    <div>
      <h3 style={{ marginBottom: 8, fontSize: 18 }}>Cross-System Timeline</h3>
      <div style={{ fontSize: 12, color: 'var(--text-dim)', marginBottom: 16 }}>
        {entries.length} events • {multiSourceCorr.length} cross-system correlations
      </div>

      <div style={{ position: 'relative' }}>
        <div style={{ position: 'absolute', left: 16, top: 0, bottom: 0, width: 2, background: 'var(--border)' }} />

        {entries.slice(0, 50).map((entry, i) => {
          const color = sourceColor(entry.source_id)
          const isCorrelated = multiSourceCorr.some(([, ids]) => ids.includes(entry.entry_id))

          return (
            <motion.div
              key={entry.entry_id}
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.03 }}
              style={{
                display: 'flex', gap: 12, alignItems: 'flex-start',
                padding: '8px 0 8px 40px', position: 'relative',
                borderLeft: isCorrelated ? `2px solid ${color}` : undefined,
                marginLeft: isCorrelated ? 15 : 0,
              }}
            >
              <div style={{
                position: 'absolute', left: isCorrelated ? 9 : 12, top: 14,
                width: 10, height: 10, borderRadius: '50%',
                background: color, border: '2px solid var(--bg-dark)',
              }} />

              <span className="timestamp" style={{ minWidth: 100 }}>{formatTime(entry.written_ts)}</span>
              <SourceBadge source={entry.source_id} />
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color, minWidth: 220 }}>
                {entry.entry_type}
              </span>
              <span style={{ fontSize: 12, color: 'var(--text-secondary)', flex: 1 }}>
                {entryDetail(entry)}
              </span>
              {entry.correlation_id && (
                <span className="hash" style={{ fontSize: 10 }}>
                  {entry.correlation_id.slice(0, 12)}
                </span>
              )}
            </motion.div>
          )
        })}
      </div>
    </div>
  )
}
