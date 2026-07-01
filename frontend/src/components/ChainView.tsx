import { motion } from 'motion/react'
import { ChainInfo } from '../api/ledgerApi'
import { useFetch } from '../hooks/useLedger'
import { api } from '../api/ledgerApi'
import { sourceColor, sourceName } from './SourceBadge'
import { useState } from 'react'

function ChainRow({ chain, index }: { chain: ChainInfo; index: number }) {
  const [expanded, setExpanded] = useState(false)
  const color = sourceColor(chain.source)
  const topEntries = expanded ? chain.entries : chain.entries.slice(0, 6)

  return (
    <motion.div
      initial={{ opacity: 0, x: -30 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.08 }}
      className="card"
      style={{ marginBottom: 12 }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: expanded ? 16 : 0, cursor: 'pointer' }}
           onClick={() => setExpanded(!expanded)}>
        <div style={{ width: 8, height: 8, borderRadius: '50%', background: color }} />
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color, flex: 1 }}>{chain.entry_type}</span>
        <span style={{ fontSize: 11, color: 'var(--text-dim)' }}>{chain.count} entries</span>
        <span style={{ fontSize: 11, color: 'var(--text-dim)' }}>{sourceName(chain.source)}</span>
        <span style={{ fontSize: 11, color: 'var(--text-dim)' }}>{expanded ? '▲' : '▼'}</span>
      </div>

      {expanded && (
        <div style={{ display: 'flex', gap: 8, overflowX: 'auto', paddingBottom: 8 }}>
          {topEntries.map((entry, i) => (
            <motion.div
              key={entry.entry_id}
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: i * 0.05 }}
              style={{
                minWidth: 140, padding: '10px 12px', background: 'var(--surface-2)',
                border: `1px solid ${color}30`, borderRadius: 'var(--radius-md)', flexShrink: 0,
              }}
            >
              <div style={{ fontSize: 10, color: 'var(--text-dim)', marginBottom: 4 }}>#{entry.chain_position}</div>
              <div className="hash" style={{ color, marginBottom: 2 }}>{entry.entry_hash.slice(0, 16)}...</div>
              <div className="hash">← {entry.previous_hash.slice(0, 12)}...</div>
              {i < topEntries.length - 1 && (
                <div style={{ position: 'absolute', right: -12, top: '50%', color: 'var(--text-dim)', fontSize: 14 }}>→</div>
              )}
            </motion.div>
          ))}
          {chain.count > 6 && !expanded && (
            <div style={{ minWidth: 80, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-dim)', fontSize: 12 }}>
              +{chain.count - 6} more
            </div>
          )}
        </div>
      )}
    </motion.div>
  )
}

export function ChainView() {
  const { data: chains, loading } = useFetch(() => api.chains(), [])

  if (loading) return <div style={{ padding: 32, color: 'var(--text-dim)' }}>Loading chains...</div>
  if (!chains) return null

  const displayChains = chains.filter(c =>
    !c.entry_type.startsWith('test.') &&
    !c.entry_type.startsWith('test\'') &&
    !c.entry_type.startsWith('are.') &&
    c.source !== 'unknown' || c.entry_type.startsWith('gov.')
  )

  return (
    <div>
      <h3 style={{ marginBottom: 16, fontSize: 18 }}>Hash Chains ({displayChains.length})</h3>
      {displayChains.map((chain, i) => (
        <ChainRow key={chain.entry_type} chain={chain} index={i} />
      ))}
    </div>
  )
}
