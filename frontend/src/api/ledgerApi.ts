const BASE = '/api'

export interface LedgerEntry {
  entry_id: string
  entry_type: string
  agent_id: string
  content_raw: string
  content: Record<string, unknown> | null
  content_type: string
  source_id: string
  correlation_id: string
  entry_hash: string
  previous_hash: string
  chain_position: number
  written_ts: number
}

export interface ChainInfo {
  entry_type: string
  count: number
  source: string
  entries: LedgerEntry[]
}

export interface VerifyResult {
  entry_type: string
  chain_valid: boolean
  entries_checked: number
  failure_reason: string
}

export interface Summary {
  total_entries: number
  sources: Record<string, number>
  chain_types: number
  correlation_ids: number
  cross_system_correlations: number
}

export interface DriftGap {
  entry_id: string
  correlation_id: string
  agent_id: string
  source_id: string
  entry_type: string
  detail: string
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`)
  return res.json()
}

export const api = {
  entries: (params?: Record<string, string>) => {
    const qs = params ? '?' + new URLSearchParams(params).toString() : ''
    return get<LedgerEntry[]>(`/entries${qs}`)
  },
  summary: () => get<Summary>('/summary'),
  chains: () => get<ChainInfo[]>('/chains'),
  verify: () => get<{ all_valid: boolean; chains: VerifyResult[] }>('/verify'),
  verifyChain: (type: string) => get<VerifyResult>(`/verify/${type}`),
  timeline: () => get<{ entries: LedgerEntry[]; correlations: Record<string, string[]> }>('/timeline'),
  drift: () => get<{ gaps: DriftGap[]; total_denials: number; total_scope_evals: number }>('/drift'),
}
