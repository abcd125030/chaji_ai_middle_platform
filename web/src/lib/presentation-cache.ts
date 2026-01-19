// presentation-cache.ts 在客户端运行，使用 console 而不是 server-logger

interface PresentationProjectCache {
  projectId: string
  project: unknown  // 完整的project数据，包含pages和details
  timestamp: number
  expiry: number
}

class PresentationCache {
  private dbName = 'PresentationCache'
  private version = 2  // 升级版本以重建数据库
  private storeName = 'projects'
  private db: IDBDatabase | null = null
  private cacheExpiry = 10 * 60 * 1000 // 10分钟过期时间

  async init(): Promise<void> {
    if (this.db) return

    return new Promise((resolve, reject) => {
      const request = indexedDB.open(this.dbName, this.version)

      request.onerror = () => {
        console.error('IndexedDB 打开失败:', request.error)
        reject(request.error)
      }

      request.onsuccess = () => {
        this.db = request.result
        console.log('IndexedDB 初始化成功')
        resolve()
      }

      request.onupgradeneeded = (event) => {
        const db = (event.target as IDBOpenDBRequest).result
        
        // 创建对象存储
        if (!db.objectStoreNames.contains(this.storeName)) {
          const store = db.createObjectStore(this.storeName, { keyPath: 'projectId' })
          store.createIndex('timestamp', 'timestamp', { unique: false })
          store.createIndex('expiry', 'expiry', { unique: false })
        }
      }
    })
  }

  async getProject(projectId: string): Promise<unknown | null> {
    await this.init()
    
    if (!this.db) {
      console.error('数据库未初始化')
      return null
    }

    return new Promise((resolve) => {
      const transaction = this.db!.transaction([this.storeName], 'readonly')
      const store = transaction.objectStore(this.storeName)
      const request = store.get(projectId)

      request.onsuccess = () => {
        const result = request.result as PresentationProjectCache | undefined
        
        if (!result) {
          console.log('缓存未命中:', projectId)
          resolve(null)
          return
        }

        const now = Date.now()
        
        // 检查是否过期
        if (now > result.expiry) {
          console.log('缓存已过期:', projectId)
          // 删除过期缓存
          this.deleteProject(projectId)
          resolve(null)
          return
        }

        console.log('缓存命中:', projectId, '剩余有效期:', Math.round((result.expiry - now) / 1000), '秒')
        resolve(result.project)
      }

      request.onerror = () => {
        console.error('读取缓存失败:', request.error)
        resolve(null)
      }
    })
  }

  async setProject(projectId: string, project: unknown): Promise<void> {
    await this.init()
    
    if (!this.db) {
      console.error('数据库未初始化')
      return
    }

    const now = Date.now()
    const cacheData: PresentationProjectCache = {
      projectId,
      project,
      timestamp: now,
      expiry: now + this.cacheExpiry
    }

    return new Promise((resolve, reject) => {
      const transaction = this.db!.transaction([this.storeName], 'readwrite')
      const store = transaction.objectStore(this.storeName)
      const request = store.put(cacheData)

      request.onsuccess = () => {
        console.log('缓存保存成功:', projectId)
        resolve()
      }

      request.onerror = () => {
        console.error('缓存保存失败:', request.error)
        reject(request.error)
      }
    })
  }

  async deleteProject(projectId: string): Promise<void> {
    await this.init()
    
    if (!this.db) return

    return new Promise((resolve) => {
      const transaction = this.db!.transaction([this.storeName], 'readwrite')
      const store = transaction.objectStore(this.storeName)
      const request = store.delete(projectId)

      request.onsuccess = () => {
        console.log('缓存删除成功:', projectId)
        resolve()
      }

      request.onerror = () => {
        console.error('缓存删除失败:', request.error)
        resolve()
      }
    })
  }

  async clearExpired(): Promise<void> {
    await this.init()
    
    if (!this.db) return

    const now = Date.now()
    
    return new Promise((resolve) => {
      const transaction = this.db!.transaction([this.storeName], 'readwrite')
      const store = transaction.objectStore(this.storeName)
      const index = store.index('expiry')
      const range = IDBKeyRange.upperBound(now)
      const request = index.openCursor(range)

      request.onsuccess = () => {
        const cursor = request.result
        if (cursor) {
          console.log('删除过期缓存:', cursor.value.projectId)
          cursor.delete()
          cursor.continue()
        } else {
          resolve()
        }
      }

      request.onerror = () => {
        console.error('清理过期缓存失败:', request.error)
        resolve()
      }
    })
  }

  async clearAll(): Promise<void> {
    await this.init()
    
    if (!this.db) return

    return new Promise((resolve) => {
      const transaction = this.db!.transaction([this.storeName], 'readwrite')
      const store = transaction.objectStore(this.storeName)
      const request = store.clear()

      request.onsuccess = () => {
        console.log('所有缓存已清除')
        resolve()
      }

      request.onerror = () => {
        console.error('清除缓存失败:', request.error)
        resolve()
      }
    })
  }

  // 获取缓存统计信息
  async getCacheStats(): Promise<{
    totalCached: number
    totalSize: number
    oldestCache: Date | null
  }> {
    await this.init()
    
    if (!this.db) {
      return { totalCached: 0, totalSize: 0, oldestCache: null }
    }

    return new Promise((resolve) => {
      const transaction = this.db!.transaction([this.storeName], 'readonly')
      const store = transaction.objectStore(this.storeName)
      const request = store.getAll()

      request.onsuccess = () => {
        const results = request.result as PresentationProjectCache[]
        
        if (results.length === 0) {
          resolve({ totalCached: 0, totalSize: 0, oldestCache: null })
          return
        }

        const totalSize = JSON.stringify(results).length
        const oldestTimestamp = Math.min(...results.map(r => r.timestamp))
        
        resolve({
          totalCached: results.length,
          totalSize,
          oldestCache: new Date(oldestTimestamp)
        })
      }

      request.onerror = () => {
        resolve({ totalCached: 0, totalSize: 0, oldestCache: null })
      }
    })
  }
}

// 导出单例实例
export const presentationCache = new PresentationCache()

// 包装函数：获取带缓存的项目数据
export async function getCachedProject(
  projectId: string, 
  fetcher: () => Promise<Response>
): Promise<unknown> {
  try {
    // 先尝试从缓存获取
    const cached = await presentationCache.getProject(projectId)
    if (cached) {
      return cached
    }

    // 缓存未命中或已过期，发起请求
    console.log('项目缓存未命中，发起网络请求')
    const response = await fetcher()
    
    if (!response.ok) {
      throw new Error('获取项目数据失败')
    }

    const project = await response.json()
    
    // 保存到缓存
    await presentationCache.setProject(projectId, project)
    
    return project
  } catch (error) {
    console.error('获取项目数据错误:', error)
    // 如果网络请求失败，再次尝试从缓存获取（即使过期）
    const cached = await presentationCache.getProject(projectId)
    if (cached) {
      console.log('使用过期缓存作为降级方案')
      return cached
    }
    throw error
  }
}

// 主动刷新缓存
export async function refreshProjectCache(
  projectId: string,
  fetcher: () => Promise<Response>
): Promise<unknown> {
  try {
    // 先删除旧缓存
    await presentationCache.deleteProject(projectId)
    
    // 发起新请求
    const response = await fetcher()
    
    if (!response.ok) {
      throw new Error('刷新项目数据失败')
    }

    const project = await response.json()
    
    // 保存到缓存
    await presentationCache.setProject(projectId, project)
    
    return project
  } catch (error) {
    console.error('刷新项目数据错误:', error)
    throw error
  }
}

// 兼容旧的API（将在迁移后删除）
export async function getCachedPages(
  projectId: string, 
  fetcher: () => Promise<Response>
): Promise<unknown[]> {
  // 直接从项目缓存中获取pages
  const project = await getCachedProject(projectId, fetcher) as Record<string, unknown> | null
  return (project?.details || project?.pages || []) as unknown[]
}