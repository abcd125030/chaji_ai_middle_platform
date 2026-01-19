'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { 
  FolderIcon,
  PlusIcon,
  Cog6ToothIcon,
  CheckIcon,
  ShareIcon,
  TrashIcon,
  DocumentTextIcon,
  ChevronRightIcon,
  DocumentDuplicateIcon
} from '@heroicons/react/24/outline'
import toast from 'react-hot-toast'
import { authFetch } from '@/lib/auth-fetch'
import RouteGuard from '@/components/ui/RouteGuard'

// 项目类型定义
interface Project {
  id: string
  project_name: string
  project_description: string
  is_public: boolean
  pages?: Array<{ id: string; title: string }>
  created_at: string
  updated_at: string
}

// 计算相对时间
function getRelativeTime(dateString: string): string {
  const date = new Date(dateString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60))
  const diffMinutes = Math.floor(diffMs / (1000 * 60))
  
  if (diffDays > 7) {
    return date.toLocaleDateString('en-US')
  } else if (diffDays > 0) {
    return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`
  } else if (diffHours > 0) {
    return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`
  } else if (diffMinutes > 0) {
    return `${diffMinutes} minute${diffMinutes > 1 ? 's' : ''} ago`
  } else {
    return 'Just now'
  }
}

export default function ProjectListPage() {
  const router = useRouter()
  const [projects, setProjects] = useState<Project[]>([])
  const [isManageMode, setIsManageMode] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [deleteConfirm, setDeleteConfirm] = useState<{ show: boolean; projectId: string | null; projectName: string }>({
    show: false,
    projectId: null,
    projectName: ''
  })

  // 获取项目列表
  useEffect(() => {
    fetchProjects()
  }, [])

  const fetchProjects = async () => {
    try {
      setIsLoading(true)
      setError(null)
      
      // 使用 authFetch 进行认证请求
      const response = await authFetch('/api/presentation/projects', {
        method: 'GET',
      })

      if (!response.ok) {
        if (response.status === 401) {
          // 未登录，跳转到登录页
          const basePath = process.env.NEXT_PUBLIC_BASE_PATH || ''
          const currentPath = window.location.pathname + window.location.search
          const callbackUrl = encodeURIComponent(currentPath)
          window.location.href = `${basePath}/auth/login?callbackUrl=${callbackUrl}`
          return
        }
        const error = await response.json()
        throw new Error(error.error || 'Failed to fetch project list')
      }

      const data = await response.json()
      setProjects(data)
    } catch (err) {
      console.error('Failed to fetch project list:', err)
      setError(err instanceof Error ? err.message : 'Failed to fetch project list')
    } finally {
      setIsLoading(false)
    }
  }

  const handleDeleteProject = async () => {
    if (!deleteConfirm.projectId) return
    
    try {
      // 使用 authFetch 进行认证请求
      const response = await authFetch(`/api/presentation/projects/${deleteConfirm.projectId}`, {
        method: 'DELETE',
      })

      if (response.ok) {
        // 删除成功，更新本地状态
        setProjects(projects.filter(p => p.id !== deleteConfirm.projectId))
        setDeleteConfirm({ show: false, projectId: null, projectName: '' })
        
        // 显示成功提示
        console.log('Project deleted successfully')
      } else {
        // 获取错误信息
        const errorData = await response.json().catch(() => null)
        const errorMessage = errorData?.detail || errorData?.error || 'Failed to delete project'
        console.error('Failed to delete project:', errorMessage)
        
        // Show error message to user
        alert(`Delete failed: ${errorMessage}`)
      }
    } catch (error) {
      console.error('Delete project request failed:', error)
      alert('An error occurred while deleting the project, please try again later')
    }
  }

  const showDeleteConfirm = (projectId: string, projectName: string) => {
    setDeleteConfirm({ show: true, projectId, projectName })
  }

  const handleCloneProject = async (e: React.MouseEvent, projectId: string) => {
    e.preventDefault()
    e.stopPropagation()
    
    try {
      // 显示加载提示
      const loadingToast = toast.loading('Cloning project...', {
        position: 'top-center',
      })
      
      // 调用克隆接口
      const response = await authFetch(`/api/presentation/projects/${projectId}/clone`, {
        method: 'POST',
      })
      
      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.error || 'Failed to clone project')
      }
      
      await response.json() // 确保响应被正确读取
      
      // 更新项目列表
      await fetchProjects()
      
      // 关闭加载提示
      toast.dismiss(loadingToast)
      
      // 显示成功提示
      toast.success('Project cloned successfully', {
        position: 'top-center',
        duration: 3000,
      })
    } catch (error) {
      console.error('Failed to clone project:', error)
      toast.error(error instanceof Error ? error.message : 'Failed to clone project', {
        position: 'top-center',
        duration: 3000,
      })
    }
  }

  const handleShareProject = async (e: React.MouseEvent, project: Project) => {
    e.preventDefault()
    e.stopPropagation()
    
    try {
      // 如果项目未公开，先设置为公开
      if (!project.is_public) {
        // 使用 authFetch 进行认证请求
        const response = await authFetch(`/api/presentation/projects/${project.id}`, {
          method: 'PATCH',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ is_public: true })
        })
        
        if (!response.ok) {
          throw new Error('Failed to set project as public')
        }
        
        // 更新本地状态
        setProjects(projects.map(p => 
          p.id === project.id ? { ...p, is_public: true } : p
        ))
      }
      
      // 生成分享链接并复制到剪贴板
      const basePath = process.env.NEXT_PUBLIC_BASE_PATH || ''
      const baseUrl = process.env.NEXT_PUBLIC_BASE_URL || window.location.origin
      const shareUrl = `${baseUrl}${basePath}/presentation/share/${project.id}`
      
      // 尝试复制到剪贴板
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(shareUrl)
        toast.success('Share link copied to clipboard', {
          position: 'top-center',
          duration: 3000,
        })
      } else {
        // 降级方案：创建临时文本框
        const textArea = document.createElement('textarea')
        textArea.value = shareUrl
        textArea.style.position = 'fixed'
        textArea.style.left = '-999999px'
        document.body.appendChild(textArea)
        textArea.focus()
        textArea.select()
        try {
          document.execCommand('copy')
          toast.success('Share link copied to clipboard', {
            position: 'top-center',
            duration: 3000,
          })
        } catch (err) {
          toast.error('Failed to copy, please copy the link manually', {
            position: 'top-center',
            duration: 3000,
          })
          console.error('Copy failed:', err)
        }
        document.body.removeChild(textArea)
      }
    } catch (error) {
      console.error('Failed to share project:', error)
      toast.error('Share failed, please try again', {
        position: 'top-center',
        duration: 3000,
      })
    }
  }

  // 显示加载状态
  if (isLoading) {
    return (
      <RouteGuard>
        <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: 'var(--background)' }}>
          <div className="text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 mx-auto mb-4" style={{ borderColor: 'var(--accent)' }}></div>
            <p className="text-sm opacity-70" style={{ color: 'var(--foreground)' }}>Loading project list...</p>
          </div>
        </div>
      </RouteGuard>
    )
  }

  // 显示错误状态
  if (error) {
    return (
      <RouteGuard>
        <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: 'var(--background)' }}>
          <div className="text-center">
            <p className="text-red-500 mb-4">{error}</p>
            <button
              onClick={fetchProjects}
              className="px-4 py-2 rounded-md transition-colors"
              style={{
                backgroundColor: 'var(--accent)',
                color: 'var(--foreground)',
              }}
            >
              Retry
            </button>
          </div>
        </div>
      </RouteGuard>
    )
  }

  return (
    <RouteGuard>
      <div className="min-h-screen" style={{ backgroundColor: 'var(--background)' }}>
      <div className="max-w-6xl mx-auto px-4 py-8">
        {/* 页面标题 */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold mb-2" style={{ color: 'var(--foreground)' }}>
            Presentations
          </h1>
          <p className="text-sm opacity-70" style={{ color: 'var(--foreground)' }}>
            AI-Powered Intelligent Page Generation Tool
          </p>
        </div>

        {/* 操作栏 */}
        <div className="flex justify-between items-center mb-6">
          <span className="text-sm opacity-50" style={{ color: 'var(--foreground)' }}>
            {projects.length} project{projects.length !== 1 ? 's' : ''}
          </span>
          
          {projects.length > 0 && (
            <button
              onClick={() => setIsManageMode(!isManageMode)}
              className="px-3 py-1.5 rounded-md text-sm transition-colors flex items-center space-x-2"
              style={{
                backgroundColor: isManageMode ? 'var(--accent)' : 'transparent',
                color: 'var(--foreground)',
                border: `1px solid ${isManageMode ? 'var(--accent)' : 'var(--border)'}`,
              }}
            >
              {isManageMode ? (
                <>
                  <CheckIcon className="w-4 h-4" />
                  <span>Done</span>
                </>
              ) : (
                <>
                  <Cog6ToothIcon className="w-4 h-4" />
                  <span>Manage</span>
                </>
              )}
            </button>
          )}
        </div>

        {/* 项目网格 */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {/* 新建项目卡片 */}
          <Link
            href="/presentation/projects/new"
            className="group h-[200px] rounded-lg transition-all hover:opacity-80"
            style={{
              backgroundColor: 'var(--code-bg)',
              border: '1px dashed var(--border)',
            }}
          >
            <div className="h-full flex flex-col items-center justify-center">
              <PlusIcon 
                className="w-8 h-8 mb-3 opacity-50" 
                style={{ color: 'var(--foreground)' }}
              />
              <span 
                className="text-sm opacity-70"
                style={{ color: 'var(--foreground)' }}
              >
                Create New Project
              </span>
              <span 
                className="text-xs opacity-50 mt-1"
                style={{ color: 'var(--foreground)' }}
              >
                Generate pages quickly with AI
              </span>
            </div>
          </Link>

          {/* 现有项目卡片 */}
          {projects.map((project) => (
            <div
              key={project.id}
              className={`group relative h-[200px] rounded-lg transition-all ${
                !isManageMode ? 'cursor-pointer hover:opacity-90' : ''
              }`}
              style={{
                backgroundColor: 'var(--code-bg)',
                border: '1px solid var(--border)',
              }}
              onClick={() => !isManageMode && router.push(`/presentation/projects/${project.id}/preview`)}
            >
              <div className="p-4 h-full flex flex-col">
                {/* 操作按钮 */}
                {isManageMode ? (
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      showDeleteConfirm(project.id, project.project_name || 'Untitled Project')
                    }}
                    className="absolute top-3 right-3 w-7 h-7 rounded flex items-center justify-center transition-colors hover:opacity-80"
                    style={{
                      backgroundColor: 'var(--accent)',
                      color: 'var(--foreground)',
                    }}
                  >
                    <TrashIcon className="w-4 h-4" />
                  </button>
                ) : (
                  <div className="absolute top-3 right-3 flex space-x-2 transition-opacity opacity-0 group-hover:opacity-100">
                    <button
                      onClick={(e) => handleCloneProject(e, project.id)}
                      className="w-7 h-7 rounded flex items-center justify-center"
                      style={{
                        backgroundColor: 'var(--accent)',
                        color: 'var(--foreground)',
                      }}
                      title="Clone project"
                    >
                      <DocumentDuplicateIcon className="w-4 h-4" />
                    </button>
                    <button
                      onClick={(e) => handleShareProject(e, project)}
                      className="w-7 h-7 rounded flex items-center justify-center"
                      style={{
                        backgroundColor: 'var(--accent)',
                        color: 'var(--foreground)',
                      }}
                      title="Share project"
                    >
                      <ShareIcon className="w-4 h-4" />
                    </button>
                  </div>
                )}

                {/* 项目图标和标题 */}
                <div className="flex items-start mb-2">
                  <FolderIcon 
                    className="w-5 h-5 mr-2 mt-0.5 opacity-70" 
                    style={{ color: 'var(--foreground)' }}
                  />
                  <h3 
                    className="font-semibold text-base flex-1"
                    style={{ color: 'var(--foreground)' }}
                  >
                    {project.project_name || 'Untitled Project'}
                  </h3>
                </div>

                {/* 项目描述 */}
                <p 
                  className="text-sm opacity-70 line-clamp-2 flex-1"
                  style={{ color: 'var(--foreground)' }}
                >
                  {project.project_description || 'No description'}
                </p>

                {/* 底部信息 */}
                <div 
                  className="flex items-center justify-between pt-3 mt-auto"
                  style={{ borderTop: '1px solid var(--border)' }}
                >
                  <div className="flex items-center">
                    <DocumentTextIcon 
                      className="w-4 h-4 mr-1 opacity-50" 
                      style={{ color: 'var(--foreground)' }}
                    />
                    <span 
                      className="text-xs opacity-50"
                      style={{ color: 'var(--foreground)' }}
                    >
                      {project.pages?.length || 0} page{(project.pages?.length || 0) !== 1 ? 's' : ''}
                    </span>
                  </div>
                  
                  <div className="flex items-center space-x-2">
                    <span 
                      className="text-xs opacity-50"
                      style={{ color: 'var(--foreground)' }}
                    >
                      {getRelativeTime(project.updated_at || project.created_at)}
                    </span>
                    {!isManageMode && (
                      <ChevronRightIcon 
                        className="w-3 h-3 opacity-0 group-hover:opacity-50 transition-opacity" 
                        style={{ color: 'var(--foreground)' }}
                      />
                    )}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 删除确认对话框 */}
      {deleteConfirm.show && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          {/* 背景遮罩 */}
          <div 
            className="absolute inset-0 bg-black bg-opacity-50"
            onClick={() => setDeleteConfirm({ show: false, projectId: null, projectName: '' })}
          />
          
          {/* 对话框内容 */}
          <div 
            className="relative bg-white dark:bg-gray-800 rounded-lg p-6 max-w-md w-full mx-4"
            style={{
              backgroundColor: 'var(--background)',
              border: '1px solid var(--border)',
            }}
          >
            <h3 className="text-lg font-semibold mb-2" style={{ color: 'var(--foreground)' }}>
              Confirm Delete Project
            </h3>
            
            <p className="mb-6 opacity-80" style={{ color: 'var(--foreground)' }}>
              Are you sure you want to delete the project &ldquo;<span className="font-medium">{deleteConfirm.projectName}</span>&rdquo;? This action cannot be undone.
            </p>
            
            <div className="flex justify-end space-x-3">
              <button
                onClick={() => setDeleteConfirm({ show: false, projectId: null, projectName: '' })}
                className="px-4 py-2 rounded-md transition-colors"
                style={{
                  backgroundColor: 'var(--code-bg)',
                  color: 'var(--foreground)',
                  border: '1px solid var(--border)',
                }}
              >
                Cancel
              </button>
              
              <button
                onClick={handleDeleteProject}
                className="px-4 py-2 rounded-md transition-colors hover:opacity-90"
                style={{
                  backgroundColor: '#ef4444',
                  color: 'white',
                }}
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
      </div>
    </RouteGuard>
  )
}