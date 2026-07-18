import { useCallback, useEffect, useState } from 'react'
import {
  addMcpServer,
  deleteMcpServer,
  fetchMcpPresets,
  fetchMcpServers,
  testMcpServer,
  toggleMcpServer,
  type McpPreset,
  type McpServer,
} from '../mcp'

export function useMcp(enabled: boolean) {
  const [presets, setPresets] = useState<McpPreset[]>([])
  const [servers, setServers] = useState<McpServer[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    if (!enabled) return
    setLoading(true)
    setError(null)
    try {
      const [p, s] = await Promise.all([fetchMcpPresets(), fetchMcpServers()])
      setPresets(p)
      setServers(s)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load MCP')
    } finally {
      setLoading(false)
    }
  }, [enabled])

  useEffect(() => {
    refresh()
  }, [refresh])

  const connect = async (payload: Parameters<typeof addMcpServer>[0]) => {
    setError(null)
    try {
      const server = await addMcpServer(payload)
      await refresh()
      return server
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Failed to connect MCP server'
      setError(msg)
      throw e
    }
  }

  const remove = async (id: string) => {
    setError(null)
    await deleteMcpServer(id)
    await refresh()
  }

  const test = async (id: string) => {
    setError(null)
    const result = await testMcpServer(id)
    await refresh()
    return result
  }

  const toggle = async (id: string, enabled: boolean) => {
    setError(null)
    await toggleMcpServer(id, enabled)
    await refresh()
  }

  return { presets, servers, loading, error, refresh, connect, remove, test, toggle }
}
