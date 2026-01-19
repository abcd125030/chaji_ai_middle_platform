'use client'

import { useState, useEffect, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import {
  ArrowsPointingOutIcon,
  ArrowsPointingInIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  HomeIcon
} from '@heroicons/react/24/outline'
import CodePreviewSandbox from '@/components/presentation/CodePreviewSandbox'

// 项目类型定义
interface Project {
  id: string
  project_name: string
  project_description: string
  project_style?: string
  global_style_code?: string
  pages?: Array<{ 
    id: string
    title: string
    order: number
    html?: string
    styles?: string
    script?: string
    mermaid_content?: string
  }>
  is_public: boolean
  created_at: string
  updated_at: string
}

export default function SharePage({ 
  params 
}: { 
  params: Promise<{ shareId: string }> 
}) {
  const router = useRouter()
  const [currentPageIndex, setCurrentPageIndex] = useState(0)
  const [isFullscreen, setIsFullscreen] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [project, setProject] = useState<Project | null>(null)
  const [shareId, setShareId] = useState<string>('')
  
  // 解包 params
  useEffect(() => {
    const getShareId = async () => {
      const resolvedParams = await params
      setShareId(resolvedParams.shareId)
    }
    getShareId()
  }, [params])
  
  // 获取项目数据
  const fetchProjectData = useCallback(async () => {
    try {
      setIsLoading(true)
      setError(null)
      
      // 获取公开项目数据（无需认证）
      // 使用完整路径，避免BASE_PATH影响
      const basePath = process.env.NEXT_PUBLIC_BASE_PATH || '';
      const apiPath = basePath ? `${basePath}/api/presentation/share/${shareId}` : `/api/presentation/share/${shareId}`;
      const response = await fetch(apiPath)
      
      if (!response.ok) {
        if (response.status === 404) {
          throw new Error('项目不存在或未公开')
        }
        throw new Error('获取项目失败')
      }
      
      const projectData = await response.json()
      
      if (!projectData) {
        throw new Error('获取项目失败')
      }
      
      setProject(projectData)
    } catch (err) {
      console.error('获取项目数据失败:', err)
      setError(err instanceof Error ? err.message : '获取项目失败')
    } finally {
      setIsLoading(false)
    }
  }, [shareId])
  
  useEffect(() => {
    if (shareId) {
      fetchProjectData()
    }
  }, [shareId, fetchProjectData])
  
  // 如果没有项目数据，返回加载或错误状态
  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center geometric-background">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 mx-auto mb-4" style={{ borderColor: 'var(--accent)' }}></div>
          <p className="text-sm opacity-70" style={{ color: 'var(--foreground)' }}>加载项目中...</p>
        </div>
      </div>
    )
  }
  
  if (error || !project) {
    return (
      <div className="min-h-screen flex items-center justify-center geometric-background">
        <div className="text-center">
          <p className="text-red-500 mb-4">{error || '项目不存在'}</p>
          <button
            onClick={() => router.push('/presentation')}
            className="px-4 py-2 rounded-md transition-colors"
            style={{
              backgroundColor: 'var(--accent)',
              color: 'var(--foreground)',
            }}
          >
            <HomeIcon className="w-5 h-5 inline mr-2" />
            返回首页
          </button>
        </div>
      </div>
    )
  }
  
  const pages = project.pages || []
  const currentPage = pages[currentPageIndex]

  const handlePrevPage = () => {
    if (currentPageIndex > 0) {
      setCurrentPageIndex(currentPageIndex - 1)
    }
  }

  const handleNextPage = () => {
    if (currentPageIndex < pages.length - 1) {
      setCurrentPageIndex(currentPageIndex + 1)
    }
  }

  const toggleFullscreen = () => {
    setIsFullscreen(!isFullscreen)
  }

  return (
    <div className={`${isFullscreen ? 'fixed inset-0 z-50' : 'h-screen'} flex flex-col overflow-hidden`} style={{ backgroundColor: 'var(--background)' }}>
      {/* 顶部工具栏 */}
      <div className="px-4 py-3" style={{ backgroundColor: 'var(--code-bg)', borderBottom: '1px solid var(--border)' }}>
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <button
              onClick={() => router.push('/')}
              className="opacity-70 hover:opacity-100 transition-opacity"
              style={{ color: 'var(--foreground)' }}
            >
              <HomeIcon className="w-5 h-5" />
            </button>
            <div>
              <h1 className="font-semibold" style={{ color: 'var(--foreground)' }}>
                {project.project_name}
                <span className="ml-2 text-xs px-2 py-1 rounded-full opacity-70" style={{ backgroundColor: 'var(--accent)' }}>
                  公开分享
                </span>
              </h1>
              <p className="text-sm opacity-70" style={{ color: 'var(--foreground)' }}>
                {pages.length > 0 ? (
                  <>第 {currentPageIndex + 1} 页 / 共 {pages.length} 页 - {currentPage?.title}</>
                ) : (
                  '暂无页面'
                )}
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-2">
            <button
              onClick={toggleFullscreen}
              className="p-2 rounded opacity-70 hover:opacity-100 transition-opacity"
              style={{ color: 'var(--foreground)' }}
              title={isFullscreen ? '退出全屏' : '全屏'}
            >
              {isFullscreen ? <ArrowsPointingInIcon className="w-5 h-5" /> : <ArrowsPointingOutIcon className="w-5 h-5" />}
            </button>
          </div>
        </div>
      </div>

      {/* 页面标签栏 - 桌面版 */}
      {!isFullscreen && pages.length > 0 && (
        <div className="hidden md:block overflow-x-auto" style={{ backgroundColor: 'var(--code-bg)', borderBottom: '1px solid var(--border)' }}>
          <div className="flex items-center px-4 py-2 min-w-max">
            {/* 页面标签 */}
            <div className="flex items-center space-x-1">
              {pages.map((page, index) => (
                <button
                  key={page.id}
                  onClick={() => setCurrentPageIndex(index)}
                  className="px-4 py-2 rounded-t-lg transition-all flex items-center space-x-2 whitespace-nowrap"
                  style={{
                    backgroundColor: index === currentPageIndex ? 'var(--background)' : 'transparent',
                    color: 'var(--foreground)',
                    opacity: index === currentPageIndex ? 1 : 0.7,
                    borderTop: index === currentPageIndex ? '2px solid var(--foreground)' : '2px solid transparent',
                    borderLeft: index === currentPageIndex ? '1px solid var(--border)' : '1px solid transparent',
                    borderRight: index === currentPageIndex ? '1px solid var(--border)' : '1px solid transparent',
                    marginBottom: index === currentPageIndex ? '-1px' : '0'
                  }}
                >
                  <span className="text-xs opacity-50">{index + 1}</span>
                  <span className="text-sm">{page.title}</span>
                </button>
              ))}
            </div>

            {/* 页面计数器 */}
            <div className="ml-auto flex items-center space-x-2 px-4">
              <span className="text-xs opacity-50" style={{ color: 'var(--foreground)' }}>
                {currentPageIndex + 1} / {pages.length}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* 页面导航栏 - 移动版 */}
      {!isFullscreen && pages.length > 0 && (
        <div className="md:hidden" style={{ backgroundColor: 'var(--code-bg)', borderBottom: '1px solid var(--border)' }}>
          <div className="flex items-center justify-between px-4 py-2">
            {/* 页面选择下拉框 */}
            <div className="flex items-center space-x-2 flex-1">
              <select
                value={currentPageIndex}
                onChange={(e) => setCurrentPageIndex(Number(e.target.value))}
                className="px-3 py-1.5 rounded-lg text-sm flex-1 max-w-xs"
                style={{
                  backgroundColor: 'var(--background)',
                  color: 'var(--foreground)',
                  border: '1px solid var(--border)'
                }}
              >
                {pages.map((page, index) => (
                  <option key={page.id} value={index}>
                    {index + 1}. {page.title}
                  </option>
                ))}
              </select>
              
              {/* 快速导航按钮 */}
              <button
                onClick={handlePrevPage}
                disabled={currentPageIndex === 0}
                className="p-1.5 rounded disabled:opacity-30"
                style={{ color: 'var(--foreground)' }}
              >
                <ChevronLeftIcon className="w-4 h-4" />
              </button>
              <button
                onClick={handleNextPage}
                disabled={currentPageIndex === pages.length - 1}
                className="p-1.5 rounded disabled:opacity-30"
                style={{ color: 'var(--foreground)' }}
              >
                <ChevronRightIcon className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 主要内容区域 */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* 预览区域 */}
        <div className="flex-1 relative overflow-hidden" style={{ backgroundColor: 'var(--code-bg)' }}>
          {pages.length === 0 ? (
            // 无页面时的提示
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="text-center">
                <p className="text-lg mb-4 opacity-70" style={{ color: 'var(--foreground)' }}>
                  此项目还没有页面
                </p>
              </div>
            </div>
          ) : (
            <>
              {/* 导航按钮 */}
              <button
                onClick={handlePrevPage}
                disabled={currentPageIndex === 0}
                className={`absolute left-4 top-1/2 -translate-y-1/2 z-10 p-2 rounded-full disabled:opacity-50 disabled:cursor-not-allowed ${
                  isFullscreen ? 'block' : 'hidden md:block'
                }`}
                style={{
                  backgroundColor: 'var(--accent)',
                  color: 'var(--foreground)',
                  border: '1px solid var(--border)'
                }}
              >
                <ChevronLeftIcon className="w-6 h-6" />
              </button>
              <button
                onClick={handleNextPage}
                disabled={currentPageIndex === pages.length - 1}
                className={`absolute right-4 top-1/2 -translate-y-1/2 z-10 p-2 rounded-full disabled:opacity-50 disabled:cursor-not-allowed ${
                  isFullscreen ? 'block' : 'hidden md:block'
                }`}
                style={{
                  backgroundColor: 'var(--accent)',
                  color: 'var(--foreground)',
                  border: '1px solid var(--border)'
                }}
              >
                <ChevronRightIcon className="w-6 h-6" />
              </button>

              {/* 使用沙盒组件预览 */}
              <div className="absolute inset-0 w-full h-full">
                <CodePreviewSandbox
                  htmlContent={currentPage?.html || ''}
                  cssContent={currentPage?.styles || ''}
                  jsContent={currentPage?.script || ''}
                  globalStyleCode={project.global_style_code || ''}
                  mermaidContent={currentPage?.mermaid_content || ''}
                  isFullscreen={false}
                  showFullscreenControl={false}
                  showDownloadControl={false}
                />
              </div>
            </>
          )}
        </div>
      </div>

      {/* 底部页面指示器（全屏模式） */}
      {isFullscreen && pages.length > 0 && (
        <div className="absolute bottom-4 left-1/2 -translate-x-1/2 flex space-x-2">
          {pages.map((_, index) => (
            <button
              key={index}
              onClick={() => setCurrentPageIndex(index)}
              className="w-2 h-2 rounded-full transition-opacity"
              style={{
                backgroundColor: 'var(--foreground)',
                opacity: index === currentPageIndex ? 1 : 0.4
              }}
            />
          ))}
        </div>
      )}
    </div>
  )
}