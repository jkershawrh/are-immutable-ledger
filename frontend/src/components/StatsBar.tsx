import { motion } from 'motion/react'
import { Summary } from '../api/ledgerApi'

export function StatsBar({ summary }: { summary: Summary | null }) {
  if (!summary) return null
  const stats = [
    { value: summary.total_entries, label: 'Entries' },
    { value: Object.keys(summary.sources).length, label: 'Sources' },
    { value: summary.chain_types, label: 'Chains' },
    { value: summary.cross_system_correlations, label: 'Cross-System' },
  ]
  return (
    <div className="stats-row">
      {stats.map((s, i) => (
        <motion.div
          key={s.label}
          className="stat-card"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: i * 0.1 }}
        >
          <div className="stat-value">{s.value}</div>
          <div className="stat-label">{s.label}</div>
        </motion.div>
      ))}
    </div>
  )
}
