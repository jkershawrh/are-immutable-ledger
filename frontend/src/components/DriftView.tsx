import { motion } from 'motion/react'
import { useFetch } from '../hooks/useLedger'
import { api } from '../api/ledgerApi'

export function DriftView() {
  const { data, loading } = useFetch(() => api.drift(), [])

  if (loading) return <div style={{ padding: 32, color: 'var(--text-dim)' }}>Analyzing drift...</div>
  if (!data) return null

  return (
    <div>
      <h3 style={{ marginBottom: 8, fontSize: 18 }}>Drift Detection</h3>
      <div style={{ fontSize: 12, color: 'var(--text-dim)', marginBottom: 24 }}>
        Checked {data.total_denials} denials against {data.total_scope_evals} scope evaluations
      </div>

      {data.gaps.length === 0 ? (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="card"
          style={{ textAlign: 'center', padding: 40, border: '1px solid var(--green-border)', background: 'var(--green-bg)' }}
        >
          <div style={{ fontSize: 20, fontWeight: 700, color: 'var(--green)' }}>No Authorization Gaps</div>
          <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 8 }}>
            All denials have matching scope evaluations
          </div>
        </motion.div>
      ) : (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            style={{
              padding: 16, borderRadius: 'var(--radius-md)', marginBottom: 16,
              background: 'var(--orange-bg)', border: '1px solid var(--orange-border)',
            }}
          >
            <span style={{ color: 'var(--orange)', fontWeight: 700, fontSize: 15 }}>
              {data.gaps.length} Authorization Gap{data.gaps.length > 1 ? 's' : ''} Detected
            </span>
          </motion.div>

          {data.gaps.map((gap, i) => (
            <motion.div
              key={gap.entry_id}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.1 }}
              className="card"
              style={{
                marginBottom: 12, borderColor: 'var(--orange-border)',
                borderLeft: '3px solid var(--orange)',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                <motion.div
                  animate={{ opacity: [1, 0.4, 1] }}
                  transition={{ duration: 1.5, repeat: Infinity }}
                  style={{
                    width: 10, height: 10, borderRadius: '50%', background: 'var(--orange)',
                  }}
                />
                <span style={{ fontFamily: 'var(--font-display)', fontWeight: 700, color: 'var(--orange)' }}>GAP</span>
                <span style={{ fontSize: 13, color: 'var(--text-primary)' }}>{gap.detail}</span>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, fontSize: 12 }}>
                <div><span style={{ color: 'var(--text-dim)' }}>Agent:</span> <span style={{ color: 'var(--text-secondary)' }}>{gap.agent_id}</span></div>
                <div><span style={{ color: 'var(--text-dim)' }}>Source:</span> <span style={{ color: 'var(--text-secondary)' }}>{gap.source_id}</span></div>
                <div><span style={{ color: 'var(--text-dim)' }}>Correlation:</span> <span className="hash">{gap.correlation_id}</span></div>
                <div><span style={{ color: 'var(--text-dim)' }}>Type:</span> <span className="hash">{gap.entry_type}</span></div>
              </div>
              <div style={{ marginTop: 8, fontSize: 11, color: 'var(--orange)', fontFamily: 'var(--font-mono)' }}>
                Denied by sandbox but no ARE scope evaluation found for this correlation
              </div>
            </motion.div>
          ))}
        </>
      )}
    </div>
  )
}
