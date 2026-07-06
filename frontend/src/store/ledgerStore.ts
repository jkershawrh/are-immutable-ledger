import { create } from 'zustand'
import { api, LedgerEntry, ChainInfo, Summary, DriftGap } from '../api/ledgerApi'

interface LedgerStore {
  entries: LedgerEntry[]
  chains: ChainInfo[]
  summary: Summary | null
  driftGaps: DriftGap[]

  selectedSource: string | null
  selectedCorrelation: string | null
  selectedEntryId: string | null

  loading: boolean
  lastFetch: number
  mode: 'explorer' | 'tour'

  fetchAll: () => Promise<void>
  selectSource: (source: string | null) => void
  selectCorrelation: (id: string | null) => void
  selectEntry: (id: string | null) => void
  setMode: (mode: 'explorer' | 'tour') => void
}

export const useLedgerStore = create<LedgerStore>((set, get) => ({
  entries: [],
  chains: [],
  summary: null,
  driftGaps: [],

  selectedSource: null,
  selectedCorrelation: null,
  selectedEntryId: null,

  loading: false,
  lastFetch: 0,
  mode: 'explorer',

  fetchAll: async () => {
    const now = Date.now()
    if (now - get().lastFetch < 5000) return
    set({ loading: true })
    try {
      const [entries, chains, summary, drift] = await Promise.all([
        api.entries(),
        api.chains(),
        api.summary(),
        api.drift(),
      ])
      set({
        entries,
        chains: chains.filter(c =>
          !c.entry_type.startsWith('test.') &&
          !c.entry_type.startsWith("test'") &&
          !c.entry_type.startsWith('are.')
        ),
        summary,
        driftGaps: drift.gaps,
        lastFetch: now,
      })
    } finally {
      set({ loading: false })
    }
  },

  selectSource: (source) => set({ selectedSource: source }),
  selectCorrelation: (id) => set({ selectedCorrelation: id }),
  selectEntry: (id) => set({ selectedEntryId: id }),
  setMode: (mode) => set({ mode }),
}))

export function sourceColor(source: string): string {
  if (source.includes('openshell')) return '#4ade80'
  if (source.includes('kagenti')) return '#06b6d4'
  if (source.includes('gov')) return '#a78bfa'
  if (source.includes('standalone')) return '#facc15'
  return '#7a7f94'
}

export function sourceName(source: string): string {
  if (source.includes('openshell')) return 'OpenShell'
  if (source.includes('kagenti')) return 'Kagenti'
  if (source.includes('gov')) return 'Governance'
  if (source.includes('standalone')) return 'Standalone'
  return source.split('-')[0]
}
