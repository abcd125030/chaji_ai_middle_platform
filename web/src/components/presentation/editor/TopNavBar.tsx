'use client'

import { useRouter } from 'next/navigation'
import { 
  HomeIcon,
  ArrowLeftIcon,
  EyeIcon,
  PencilSquareIcon,
  ChevronLeftIcon,
  ChevronRightIcon
} from '@heroicons/react/24/outline'

interface Page {
  id: string
  title: string
  order: number
}

interface TopNavBarProps {
  projectId?: string
  projectName?: string
  pageId?: string
  pageTitle?: string
  prevPage?: Page | null
  nextPage?: Page | null
  mode?: 'preview' | 'edit' | 'add'
  pages?: Page[]
}

export function TopNavBar({
  projectId,
  projectName,
  pageId,
  pageTitle: _pageTitle,
  prevPage,
  nextPage,
  mode,
  pages = []
}: TopNavBarProps) {
  const router = useRouter()
  
  const handlePrevPage = () => {
    if (prevPage && projectId) {
      router.push(`/pagtive/projects/${projectId}/pages/${prevPage.id}/edit`)
    }
  }
  
  const handleNextPage = () => {
    if (nextPage && projectId) {
      router.push(`/pagtive/projects/${projectId}/pages/${nextPage.id}/edit`)
    }
  }
  
  const handlePreview = () => {
    if (projectId) {
      router.push(`/pagtive/projects/${projectId}/preview`)
    }
  }
  
  const handleEdit = () => {
    if (projectId && pageId) {
      router.push(`/pagtive/projects/${projectId}/pages/${pageId}/edit`)
    }
  }

  return (
    <div className="fixed top-0 left-0 right-0 h-12 backdrop-blur-sm border-b z-40" style={{ backgroundColor: 'var(--background)', borderColor: 'var(--border)' }}>
      <div className="h-full px-4 flex items-center justify-between">
        {/* 左侧 - 返回和项目信息 */}
        <div className="flex items-center space-x-3">
          {projectId && (
            <>
              <button
                onClick={() => router.push(`/pagtive/projects/${projectId}/preview`)}
                className="p-1 rounded transition-colors hover:bg-[var(--secondary-hover)]" style={{ color: 'var(--foreground)' }}
                title="Back to project"
              >
                <ArrowLeftIcon className="w-4 h-4" />
              </button>
              <div className="text-sm">
                <span className="opacity-50" style={{ color: 'var(--foreground)' }}>{projectName}</span>
                {/* Remove left page title, since there's already a dropdown in the middle */}
                {mode === 'add' && (
                  <>
                    <span className="opacity-30 mx-2" style={{ color: 'var(--foreground)' }}>/</span>
                    <span className="font-medium" style={{ color: 'var(--foreground)' }}>New Page</span>
                  </>
                )}
              </div>
            </>
          )}
        </div>

        {/* Center - page navigation */}
        {mode === 'edit' && pages.length > 1 && (
          <div className="flex items-center space-x-2">
            <button
              onClick={handlePrevPage}
              disabled={!prevPage}
              className="p-1 rounded disabled:opacity-30 disabled:cursor-not-allowed transition-colors hover:bg-[var(--secondary-hover)]" style={{ color: 'var(--foreground)' }}
              title="Previous page"
            >
              <ChevronLeftIcon className="w-4 h-4" />
            </button>
            
            <select
              value={pageId}
              onChange={(e) => {
                router.push(`/pagtive/projects/${projectId}/pages/${e.target.value}/edit`)
              }}
              className="px-3 py-1 text-sm rounded border" style={{ backgroundColor: 'var(--code-bg)', borderColor: 'var(--border)', color: 'var(--foreground)' }}
            >
              {pages.map(page => (
                <option key={page.id} value={page.id}>
                  {page.title || `Page ${page.id}`}
                </option>
              ))}
            </select>
            
            <button
              onClick={handleNextPage}
              disabled={!nextPage}
              className="p-1 rounded disabled:opacity-30 disabled:cursor-not-allowed transition-colors hover:bg-[var(--secondary-hover)]" style={{ color: 'var(--foreground)' }}
              title="Next page"
            >
              <ChevronRightIcon className="w-4 h-4" />
            </button>
          </div>
        )}

        {/* Right - action buttons */}
        <div className="flex items-center space-x-2">
          {mode === 'preview' && pageId && (
            <button
              onClick={handleEdit}
              className="p-1.5 rounded transition-colors hover:bg-[var(--secondary-hover)]" style={{ color: 'var(--foreground)' }}
              title="Edit page"
            >
              <PencilSquareIcon className="w-4 h-4" />
            </button>
          )}
          
          {(mode === 'edit' || mode === 'add') && (
            <button
              onClick={handlePreview}
              className="p-1.5 rounded transition-colors hover:bg-[var(--secondary-hover)]" style={{ color: 'var(--foreground)' }}
              title="Preview"
            >
              <EyeIcon className="w-4 h-4" />
            </button>
          )}
          
          <button
            onClick={() => router.push('/pagtive')}
            className="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
            title="Back to home"
          >
            <HomeIcon className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  )
}