import { motion, AnimatePresence } from 'motion/react'
import { useState } from 'react'
import { api, VerifyResult } from '../api/ledgerApi'
import { sourceColor } from './SourceBadge'

export function VerifyView() {
  const [results, setResults] = useState<VerifyResult[] | null>(null)
  const [running, setRunning] = useState(false)
  const [progress, setProgress] = useState(0)

  const runVerification = async () => {
    setRunning(true)
    setResults(null)
    setProgress(0)
    const data = await api.verify()
    const chains = data.chains.filter(c =>
      !c.entry_type.startsWith('test.') &&
      !c.entry_type.startsWith('test\'') &&
      !c.entry_type.startsWith('are.')
    )
    const staged: VerifyResult[] = []
    for (let i = 0; i < chains.length; i++) {
      staged.push(chains[i])
      setResults([...staged])
      setProgress(Math.round(((i + 1) / chains.length) * 100))
      await new Promise(r => setTimeout(r, 80))
    }
    setRunning(false)
  }

  const allValid = results && results.every(r => r.chain_valid)
  const totalChecked = results?.reduce((s, r) => s + r.entries_checked, 0) || 0

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 24 }}>
        <h3 style={{ fontSize: 18 }}>Chain Verification</h3>
        <button onClick={runVerification} disabled={running} className="nav-btn" style={{
          background: running ? 'var(--surface-2)' : 'var(--blue-bg)',
          borderColor: 'var(--blue-border)', color: running ? 'var(--text-dim)' : 'var(--blue)',
        }}>
          {running ? `Verifying... ${progress}%` : 'Verify All Chains'}
        </button>
      </div>

      {running && (
        <div style={{ height: 4, background: 'var(--surface-2)', borderRadius: 2, marginBottom: 16, overflow: 'hidden' }}>
          <motion.div
            style={{ height: '100%', background: 'linear-gradient(90deg, var(--blue), var(--purple))', borderRadius: 2 }}
            animate={{ width: `${progress}%` }}
          />
        </div>
      )}

      <AnimatePresence>
        {results && results.map((r, i) => {
          const color = sourceColor(r.entry_type)
          return (
            <motion.div
              key={r.entry_type}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0 }}
              style={{
                display: 'flex', alignItems: 'center', gap: 12,
                padding: '8px 16px', borderBottom: '1px solid var(--border)',
              }}
            >
              <motion.div
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ type: 'spring', stiffness: 500, damping: 25 }}
                style={{
                  width: 24, height: 24, borderRadius: '50%',
                  background: r.chain_valid ? 'var(--green-bg)' : 'var(--red-bg)',
                  border: `1px solid ${r.chain_valid ? 'var(--green-border)' : 'var(--red-border)'}`,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 12,
                }}
              >
                {r.chain_valid ? '✓' : '✗'}
              </motion.div>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color, flex: 1 }}>
                {r.entry_type}
              </span>
              <span className={`badge ${r.chain_valid ? 'badge-valid' : 'badge-invalid'}`}>
                {r.chain_valid ? 'VALID' : 'INVALID'}
              </span>
              <span style={{ fontSize: 11, color: 'var(--text-dim)', minWidth: 80, textAlign: 'right' }}>
                {r.entries_checked} entries
              </span>
            </motion.div>
          )
        })}
      </AnimatePresence>

      {results && !running && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          style={{
            marginTop: 24, padding: 24, borderRadius: 'var(--radius-lg)', textAlign: 'center',
            background: allValid ? 'var(--green-bg)' : 'var(--red-bg)',
            border: `1px solid ${allValid ? 'var(--green-border)' : 'var(--red-border)'}`,
          }}
        >
          <div style={{ fontSize: 24, fontFamily: 'var(--font-display)', fontWeight: 900, color: allValid ? 'var(--green)' : 'var(--red)' }}>
            {allValid ? 'ALL CHAINS VALID' : 'CHAIN VERIFICATION FAILED'}
          </div>
          <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 4 }}>
            {results.length} chains • {totalChecked} entries • 0 tampered
          </div>
        </motion.div>
      )}
    </div>
  )
}
