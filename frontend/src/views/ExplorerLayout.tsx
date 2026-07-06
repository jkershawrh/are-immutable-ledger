import { useEffect, useState } from 'react'
import { useLedgerStore } from '../store/ledgerStore'
import { StatsBar } from '../components/StatsBar'
import { DetailSidebar } from '../components/DetailSidebar'
import { SystemCanvas } from './SystemCanvas'
import { ChainTopology } from './ChainTopology'
import { CorrelationMap } from './CorrelationMap'
import { DriftTopology } from './DriftTopology'
import { VerifyView } from '../components/VerifyView'
import { TimelineView } from '../components/TimelineView'

const VIEWS = [
  { id: 'system', label: '◇ Architecture', icon: '' },
  { id: 'chains', label: '⛓ Chains', icon: '' },
  { id: 'correlations', label: '⟷ Correlations', icon: '' },
  { id: 'drift', label: '⚠ Drift', icon: '' },
  { id: 'timeline', label: '◷ Timeline', icon: '' },
  { id: 'verify', label: '✓ Verify', icon: '' },
] as const

type ViewId = typeof VIEWS[number]['id']

export function ExplorerLayout() {
  const [activeView, setActiveView] = useState<ViewId>('system')
  const fetchAll = useLedgerStore(s => s.fetchAll)
  const summary = useLedgerStore(s => s.summary)
  const selectedEntryId = useLedgerStore(s => s.selectedEntryId)
  const entries = useLedgerStore(s => s.entries)

  useEffect(() => { fetchAll() }, [fetchAll])

  const selectedEntry = selectedEntryId
    ? entries.find(e => e.entry_id === selectedEntryId) || null
    : null

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', background: 'var(--bg-dark)' }}>
      {/* View tabs */}
      <div style={{
        display: 'flex', gap: 4, padding: '8px 16px',
        borderBottom: '1px solid var(--border)', background: 'var(--surface-1)',
        overflowX: 'auto',
      }}>
        {VIEWS.map(v => (
          <button
            key={v.id}
            onClick={() => setActiveView(v.id)}
            style={{
              padding: '6px 14px', borderRadius: 6, border: '1px solid',
              borderColor: activeView === v.id ? 'var(--blue-border)' : 'var(--border)',
              background: activeView === v.id ? 'var(--blue-bg)' : 'transparent',
              color: activeView === v.id ? 'var(--blue)' : 'var(--text-secondary)',
              fontSize: 12, fontWeight: 600, fontFamily: 'var(--font-display)',
              cursor: 'pointer', whiteSpace: 'nowrap', transition: 'all 0.2s',
            }}
          >
            {v.label}
          </button>
        ))}
      </div>

      {/* Stats bar */}
      <div style={{ padding: '8px 16px' }}>
        <StatsBar summary={summary} />
      </div>

      {/* Main content area */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
        {/* Canvas */}
        <div style={{ flex: 1, position: 'relative' }}>
          {activeView === 'system' && <SystemCanvas />}
          {activeView === 'chains' && <ChainTopology />}
          {activeView === 'correlations' && <CorrelationMap />}
          {activeView === 'drift' && <DriftTopology />}
          {activeView === 'timeline' && (
            <div style={{ padding: 24, overflowY: 'auto', height: '100%' }}>
              <TimelineView />
            </div>
          )}
          {activeView === 'verify' && (
            <div style={{ padding: 24, overflowY: 'auto', height: '100%' }}>
              <VerifyView />
            </div>
          )}
        </div>

        {/* Detail sidebar */}
        {selectedEntry && <DetailSidebar entry={selectedEntry} />}
      </div>
    </div>
  )
}
