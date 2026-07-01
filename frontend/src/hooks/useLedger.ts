import { useState, useEffect } from 'react'

export function useFetch<T>(fetcher: () => Promise<T>, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setLoading(true)
    fetcher()
      .then(setData)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, deps)

  return { data, loading, error, refetch: () => fetcher().then(setData) }
}
