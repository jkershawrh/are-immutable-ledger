import { motion } from 'motion/react'

const systems = [
  { id: 'openshell', label: 'OpenShell', sub: 'OCSF Events', color: 'var(--green)', x: 100, y: 60 },
  { id: 'kagenti', label: 'Kagenti', sub: 'OTEL Spans', color: 'var(--cyan)', x: 100, y: 180 },
  { id: 'are', label: 'ARE Foundation', sub: 'Authority Decisions', color: 'var(--purple)', x: 100, y: 300 },
]

const ledger = { x: 550, y: 180, w: 200, h: 80 }

export function SystemDiagram() {
  return (
    <div className="card" style={{ padding: 32 }}>
      <h3 style={{ marginBottom: 24, fontSize: 18 }}>Architecture</h3>
      <svg width="800" height="380" viewBox="0 0 800 380">
        {systems.map((s, i) => (
          <motion.g key={s.id} initial={{ opacity: 0, x: -40 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.2 }}>
            <rect x={s.x} y={s.y} width={160} height={60} rx={8} fill="var(--surface-2)" stroke={s.color} strokeWidth={1.5} />
            <text x={s.x + 80} y={s.y + 25} textAnchor="middle" fill="var(--text-primary)" fontSize={13} fontFamily="var(--font-display)" fontWeight={700}>{s.label}</text>
            <text x={s.x + 80} y={s.y + 43} textAnchor="middle" fill="var(--text-dim)" fontSize={10} fontFamily="var(--font-mono)">{s.sub}</text>
          </motion.g>
        ))}

        {systems.map((s, i) => (
          <motion.g key={`arrow-${s.id}`} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.6 + i * 0.15 }}>
            <motion.line
              x1={260} y1={s.y + 30} x2={ledger.x} y2={ledger.y + ledger.h / 2}
              stroke={s.color} strokeWidth={1.5} strokeDasharray="4 4"
              initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ delay: 0.8 + i * 0.15, duration: 0.6 }}
            />
            <text x={380} y={s.y + 25} textAnchor="middle" fill="var(--text-dim)" fontSize={9} fontFamily="var(--font-mono)">adapter</text>
          </motion.g>
        ))}

        <motion.g initial={{ opacity: 0, scale: 0.8 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: 1.2 }}>
          <rect x={ledger.x} y={ledger.y} width={ledger.w} height={ledger.h} rx={12}
            fill="var(--surface-2)" stroke="url(#ledger-gradient)" strokeWidth={2} />
          <defs>
            <linearGradient id="ledger-gradient" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stopColor="var(--blue)" />
              <stop offset="100%" stopColor="var(--purple)" />
            </linearGradient>
          </defs>
          <text x={ledger.x + ledger.w / 2} y={ledger.y + 30} textAnchor="middle" fill="var(--text-primary)" fontSize={15} fontFamily="var(--font-display)" fontWeight={900}>
            Immutable Ledger
          </text>
          <text x={ledger.x + ledger.w / 2} y={ledger.y + 50} textAnchor="middle" fill="var(--text-dim)" fontSize={10} fontFamily="var(--font-mono)">
            SHA-256 hash chains
          </text>
        </motion.g>

        <motion.g initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 1.6 }}>
          <text x={ledger.x + ledger.w + 30} y={ledger.y + 35} fill="var(--text-dim)" fontSize={10} fontFamily="var(--font-mono)">→ proof-explorer</text>
          <text x={ledger.x + ledger.w + 30} y={ledger.y + 50} fill="var(--text-dim)" fontSize={10} fontFamily="var(--font-mono)">→ verify &amp; query</text>
        </motion.g>

        {systems.map((s, i) => (
          <motion.circle
            key={`dot-${s.id}`}
            r={4} fill={s.color}
            initial={{ cx: 260, cy: s.y + 30, opacity: 0 }}
            animate={{
              cx: [260, ledger.x],
              cy: [s.y + 30, ledger.y + ledger.h / 2],
              opacity: [0, 1, 1, 0],
            }}
            transition={{ delay: 1.5 + i * 0.3, duration: 1.2, repeat: Infinity, repeatDelay: 2 }}
          />
        ))}
      </svg>
    </div>
  )
}
