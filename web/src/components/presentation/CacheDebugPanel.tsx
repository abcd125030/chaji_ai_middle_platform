'use client'

import { useState, useEffect, useCallback } from 'react'
import { presentationCache } from '@/lib/presentation-cache'
import { 
  ArrowPathIcon,
  TrashIcon,
  ClockIcon,
  ServerIcon,
  CheckCircleIcon,
  XCircleIcon
} from '@heroicons/react/24/outline'

interface CacheStats {
  totalCached: number
  totalSize: number
  oldestCache: Date | null
}

export function CacheDebugPanel({ projectId }: { projectId: string }) {
  const [isOpen, setIsOpen] = useState(false)
  const [stats, setStats] = useState<CacheStats>({ 
    totalCached: 0, 
    totalSize: 0, 
    oldestCache: null 
  })
  const [hasCache, setHasCache] = useState(false)
  const [isRefreshing, setIsRefreshing] = useState(false)

  // Check and update cache status
  const updateCacheStatus = useCallback(async () => {
    try {
      const cached = await presentationCache.getProject(projectId)
      setHasCache(!!cached)
      
      const cacheStats = await presentationCache.getCacheStats()
      setStats(cacheStats)
    } catch (error) {
      console.error('Failed to get cache status:', error)
    }
  }, [projectId])

  // Clear current project cache
  const clearProjectCache = async () => {
    try {
      await presentationCache.deleteProject(projectId)
      await updateCacheStatus()
      console.log('Project cache cleared')
    } catch (error) {
      console.error('Failed to clear cache:', error)
    }
  }

  // Clear all cache
  const clearAllCache = async () => {
    if (confirm('Are you sure you want to clear cache for all projects?')) {
      try {
        await presentationCache.clearAll()
        await updateCacheStatus()
        console.log('All cache cleared')
      } catch (error) {
        console.error('Failed to clear cache:', error)
      }
    }
  }

  // Clean expired cache
  const clearExpiredCache = async () => {
    try {
      await presentationCache.clearExpired()
      await updateCacheStatus()
      console.log('Expired cache cleared')
    } catch (error) {
      console.error('Failed to clear expired cache:', error)
    }
  }

  // Refresh cache status
  const refreshStatus = async () => {
    setIsRefreshing(true)
    await updateCacheStatus()
    setTimeout(() => setIsRefreshing(false), 500)
  }

  useEffect(() => {
    updateCacheStatus()
    
    // Auto-update status every 30 seconds
    const interval = setInterval(updateCacheStatus, 30000)
    return () => clearInterval(interval)
  }, [projectId, updateCacheStatus])

  // Only show in development environment
  if (process.env.NODE_ENV === 'production') {
    return null
  }

  return (
    <>
      {/* Floating button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="fixed bottom-4 left-4 z-50 p-2 bg-gray-800 text-white rounded-full shadow-lg hover:bg-gray-700 transition-colors"
        title="Cache debug panel"
      >
        <ServerIcon className="w-5 h-5" />
        {hasCache && (
          <span className="absolute -top-1 -right-1 w-3 h-3 bg-green-500 rounded-full"></span>
        )}
      </button>

      {/* Debug panel */}
      {isOpen && (
        <div className="fixed bottom-16 left-4 z-50 w-80 bg-white dark:bg-gray-800 rounded-lg shadow-xl border border-gray-200 dark:border-gray-700">
          <div className="p-4">
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-semibold text-sm">IndexedDB Cache Status</h3>
              <button
                onClick={refreshStatus}
                className={`p-1 hover:bg-gray-100 dark:hover:bg-gray-700 rounded transition-all ${
                  isRefreshing ? 'animate-spin' : ''
                }`}
              >
                <ArrowPathIcon className="w-4 h-4" />
              </button>
            </div>

            {/* Current project cache status */}
            <div className="mb-3 p-2 bg-gray-50 dark:bg-gray-900 rounded">
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs text-gray-600 dark:text-gray-400">Current Project</span>
                <div className="flex items-center gap-1">
                  {hasCache ? (
                    <>
                      <CheckCircleIcon className="w-4 h-4 text-green-500" />
                      <span className="text-xs text-green-600 dark:text-green-400">Cached</span>
                    </>
                  ) : (
                    <>
                      <XCircleIcon className="w-4 h-4 text-gray-400" />
                      <span className="text-xs text-gray-500">Not Cached</span>
                    </>
                  )}
                </div>
              </div>
              <div className="text-xs text-gray-500 dark:text-gray-400 truncate">
                ID: {projectId}
              </div>
            </div>

            {/* Global statistics */}
            <div className="space-y-2 mb-3">
              <div className="flex justify-between text-xs">
                <span className="text-gray-600 dark:text-gray-400">Cached Projects</span>
                <span className="font-mono">{stats.totalCached}</span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-gray-600 dark:text-gray-400">Cache Size</span>
                <span className="font-mono">
                  {(stats.totalSize / 1024).toFixed(1)} KB
                </span>
              </div>
              {stats.oldestCache && (
                <div className="flex justify-between text-xs">
                  <span className="text-gray-600 dark:text-gray-400">Oldest Cache</span>
                  <span className="font-mono">
                    {new Date(stats.oldestCache).toLocaleTimeString()}
                  </span>
                </div>
              )}
            </div>

            {/* Action buttons */}
            <div className="space-y-2">
              {hasCache && (
                <button
                  onClick={clearProjectCache}
                  className="w-full px-3 py-1.5 text-xs bg-yellow-50 hover:bg-yellow-100 dark:bg-yellow-900/20 dark:hover:bg-yellow-900/30 text-yellow-700 dark:text-yellow-400 rounded transition-colors flex items-center justify-center gap-1"
                >
                  <TrashIcon className="w-3.5 h-3.5" />
                  Clear Current Project Cache
                </button>
              )}
              
              <button
                onClick={clearExpiredCache}
                className="w-full px-3 py-1.5 text-xs bg-blue-50 hover:bg-blue-100 dark:bg-blue-900/20 dark:hover:bg-blue-900/30 text-blue-700 dark:text-blue-400 rounded transition-colors flex items-center justify-center gap-1"
              >
                <ClockIcon className="w-3.5 h-3.5" />
                Clear Expired Cache
              </button>

              <button
                onClick={clearAllCache}
                className="w-full px-3 py-1.5 text-xs bg-red-50 hover:bg-red-100 dark:bg-red-900/20 dark:hover:bg-red-900/30 text-red-700 dark:text-red-400 rounded transition-colors flex items-center justify-center gap-1"
              >
                <TrashIcon className="w-3.5 h-3.5" />
                Clear All Cache
              </button>
            </div>

            {/* Information note */}
            <div className="mt-3 pt-3 border-t border-gray-200 dark:border-gray-700">
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Cache validity: 10 minutes<br />
                After timeout, latest data will be automatically fetched from server
              </p>
            </div>
          </div>
        </div>
      )}
    </>
  )
}