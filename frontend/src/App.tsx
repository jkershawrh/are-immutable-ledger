import { useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { Header } from './components/Header'
import { StatsBar } from './components/StatsBar'
import { SystemDiagram } from './components/SystemDiagram'
import { ChainView } from './components/ChainView'
import { TimelineView } from './components/TimelineView'
import { VerifyView } from './components/VerifyView'
import { DriftView } from './components/DriftView'
import { useFetch } from './hooks/useLedger'
import { api } from './api/ledgerApi'

const ACTS = [
  { id: 'architecture', label: 'Architecture', icon: '◇' },
  { id: 'chains', label: 'Chains', icon: '⛓' },
  { id: 'timeline', label: 'Timeline', icon: '◷' },
  { id: 'verify', label: 'Verify', icon: '✓' },
  { id: 'drift', label: 'Drift', icon: '⚠' },
]

export default function App() {
  const [activeAct, setActiveAct] = useState('architecture')
  const { data: summary } = useFetch(() => api.summary(), [])

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg-dark)' }}>
      <Header />

      <nav className="nav-bar">
        {ACTS.map(act => (
          <button
            key={act.id}
            className={`nav-btn ${activeAct === act.id ? 'active' : ''}`}
            onClick={() => setActiveAct(act.id)}
          >
            {act.icon} {act.label}
          </button>
        ))}
      </nav>

      <div className="container">
        <StatsBar summary={summary} />

        <AnimatePresence mode="wait">
          <motion.div
            key={activeAct}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            transition={{ duration: 0.3 }}
          >
            {activeAct === 'architecture' && <SystemDiagram />}
            {activeAct === 'chains' && <ChainView />}
            {activeAct === 'timeline' && <TimelineView />}
            {activeAct === 'verify' && <VerifyView />}
            {activeAct === 'drift' && <DriftView />}
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  )
}
