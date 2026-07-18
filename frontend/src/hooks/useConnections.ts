import { useState, useEffect, useCallback } from 'react'
import {
  fetchConnections,
  connectProvider,
  disconnectProvider,
  type ConnectionStatus,
} from '../connections'

export function useConnections(enabled: boolean) {
  const [connections, setConnections] = useState<ConnectionStatus[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    if (!enabled) return
    setLoading(true)
    setError(null)
    try {
      setConnections(await fetchConnections())
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load connections')
    } finally {
      setLoading(false)
    }
  }, [enabled])

  useEffect(() => {
    refresh()
  }, [refresh])

  const connect = async (provider: string, data: Record<string, string>) => {
    setError(null)
    try {
      const result = await connectProvider(provider, data)
      setConnections(result)
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Connection failed'
      setError(msg)
      throw e
    }
  }

  const disconnect = async (provider: string) => {
    setError(null)
    const result = await disconnectProvider(provider)
    setConnections(result)
  }

  return { connections, loading, error, refresh, connect, disconnect }
}
