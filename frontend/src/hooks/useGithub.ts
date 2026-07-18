import { useCallback, useEffect, useState } from 'react'
import {
  addGithubRepo,
  deleteGithubRepo,
  fetchGithubRepos,
  type GithubRepo,
} from '../github'

export function useGithub(enabled: boolean) {
  const [repos, setRepos] = useState<GithubRepo[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    if (!enabled) return
    setLoading(true)
    setError(null)
    try {
      const list = await fetchGithubRepos()
      setRepos(list)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load repos')
    } finally {
      setLoading(false)
    }
  }, [enabled])

  useEffect(() => {
    refresh()
  }, [refresh])

  useEffect(() => {
    if (!enabled) return
    const hasIndexing = repos.some((r) => r.status === 'pending' || r.status === 'indexing')
    if (!hasIndexing) return
    const timer = setInterval(refresh, 3000)
    return () => clearInterval(timer)
  }, [enabled, repos, refresh])

  const add = async (url: string, token = '', branch = 'main') => {
    setError(null)
    try {
      const repo = await addGithubRepo({ url, token, branch })
      await refresh()
      return repo
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Failed to add repo'
      setError(msg)
      throw e
    }
  }

  const remove = async (id: string) => {
    setError(null)
    await deleteGithubRepo(id)
    await refresh()
  }

  return { repos, loading, error, refresh, add, remove }
}
