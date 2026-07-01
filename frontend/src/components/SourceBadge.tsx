export function sourceColor(source: string): string {
  if (source.includes('openshell')) return 'var(--green)'
  if (source.includes('kagenti')) return 'var(--cyan)'
  if (source.includes('gov')) return 'var(--purple)'
  if (source.includes('standalone')) return 'var(--yellow)'
  return 'var(--text-dim)'
}

export function sourceClass(source: string): string {
  if (source.includes('openshell')) return 'badge-openshell'
  if (source.includes('kagenti')) return 'badge-kagenti'
  if (source.includes('gov')) return 'badge-are'
  if (source.includes('standalone')) return 'badge-standalone'
  return ''
}

export function sourceName(source: string): string {
  if (source.includes('openshell')) return 'OpenShell'
  if (source.includes('kagenti')) return 'Kagenti'
  if (source.includes('gov')) return 'Governance'
  if (source.includes('standalone')) return 'Standalone'
  return source.split('-')[0]
}

export function SourceBadge({ source }: { source: string }) {
  return <span className={`badge ${sourceClass(source)}`}>{sourceName(source)}</span>
}
