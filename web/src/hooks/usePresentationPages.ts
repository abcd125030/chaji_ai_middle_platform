import { useState, useEffect, useCallback } from 'react'
import { authFetch } from '@/lib/auth-fetch'
import { getCachedPages, refreshProjectCache, presentationCache } from '@/lib/presentation-cache'

interface UsePresentationPagesOptions {
  autoRefresh?: boolean
  onError?: (error: Error) => void
}

export function usePresentationPages(
  projectId: string | null,
  options: UsePresentationPagesOptions = {}
) {
  const { autoRefresh = false, onError } = options
  const [pages, setPages] = useState<unknown[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<Error | null>(null)
  const [lastFetch, setLastFetch] = useState<Date | null>(null)

  // 获取页面数据（使用缓存）
  const fetchPages = useCallback(async () => {
    if (!projectId) return

    setIsLoading(true)
    setError(null)

    try {
      const data = await getCachedPages(projectId, () =>
        authFetch(`/api/presentation/projects/${projectId}/pages`)
      )
      
      setPages(data || [])
      setLastFetch(new Date())
    } catch (err) {
      const error = err instanceof Error ? err : new Error('获取页面数据失败')
      setError(error)
      onError?.(error)
    } finally {
      setIsLoading(false)
    }
  }, [projectId, onError])

  // 强制刷新（清除缓存并重新获取）
  const refresh = useCallback(async () => {
    if (!projectId) return

    setIsLoading(true)
    setError(null)

    try {
      const projectData = await refreshProjectCache(projectId, () =>
        authFetch(`/api/presentation/projects/${projectId}`)
      ) as Record<string, unknown> | null
      
      const pages = (projectData?.details || projectData?.pages || []) as unknown[]
      setPages(pages)
      setLastFetch(new Date())
    } catch (err) {
      const error = err instanceof Error ? err : new Error('刷新页面数据失败')
      setError(error)
      onError?.(error)
    } finally {
      setIsLoading(false)
    }
  }, [projectId, onError])

  // 清除当前项目缓存
  const clearCache = useCallback(async () => {
    if (!projectId) return
    
    try {
      await presentationCache.deleteProject(projectId)
      setPages([])
      setLastFetch(null)
    } catch (err) {
      console.error('清除缓存失败:', err)
    }
  }, [projectId])

  // 获取缓存统计信息
  const getCacheStats = useCallback(async () => {
    return await presentationCache.getCacheStats()
  }, [])

  // 初始加载
  useEffect(() => {
    if (projectId) {
      fetchPages()
    }
  }, [projectId, fetchPages])

  // 自动刷新
  useEffect(() => {
    if (!autoRefresh || !projectId) return

    // 每5分钟自动刷新一次
    const interval = setInterval(() => {
      refresh()
    }, 5 * 60 * 1000)

    return () => clearInterval(interval)
  }, [autoRefresh, projectId, refresh])

  // 页面可见性变化时检查缓存
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible' && projectId) {
        // 页面重新可见时，检查是否需要刷新
        // 如果上次获取时间超过10分钟，自动刷新
        if (lastFetch) {
          const elapsed = Date.now() - lastFetch.getTime()
          if (elapsed > 10 * 60 * 1000) {
            fetchPages()
          }
        }
      }
    }

    document.addEventListener('visibilitychange', handleVisibilityChange)
    return () => document.removeEventListener('visibilitychange', handleVisibilityChange)
  }, [projectId, lastFetch, fetchPages])

  return {
    pages,
    isLoading,
    error,
    lastFetch,
    refresh,
    clearCache,
    getCacheStats
  }
}