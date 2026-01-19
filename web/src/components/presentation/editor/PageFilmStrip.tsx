'use client'

import { useState, useCallback, useMemo } from 'react'
import { useRouter } from 'next/navigation'
import { 
  PlusIcon,
  ChevronDoubleRightIcon,
  ChevronDoubleLeftIcon
} from '@heroicons/react/24/outline'

interface Page {
  id: string
  title: string
  order: number
}

interface PageFilmStripProps {
  projectId: string
  currentPageId?: string
  pages: Page[]
  isLoading?: boolean
  isSaving?: boolean
  mode?: 'preview' | 'edit' | 'add'
  insertAfterId?: string
  defaultExpanded?: boolean
}

export function PageFilmStrip({
  projectId,
  currentPageId,
  pages,
  isLoading = false,
  isSaving = false,
  mode = 'preview',
  insertAfterId,
  defaultExpanded = false
}: PageFilmStripProps) {
  const router = useRouter()
  const [isExpanded, setIsExpanded] = useState(defaultExpanded)
  const [isNavigating, setIsNavigating] = useState(false)
  const isAddPage = mode === 'add'
  
  // Ensure pages is an array
  const safePages = useMemo(() => Array.isArray(pages) ? pages : [], [pages])
  
  // Calculate new page insertion position
  const getNewPageIndex = useCallback(() => {
    if (!isAddPage || !insertAfterId) return -1
    
    if (safePages.length === 0) {
      return 0
    }
    
    if (insertAfterId === 'start') {
      return 0
    } else if (insertAfterId === 'end') {
      return safePages.length
    } else {
      const afterIndex = safePages.findIndex(p => p.id === insertAfterId)
      return afterIndex !== -1 ? afterIndex + 1 : -1
    }
  }, [isAddPage, insertAfterId, safePages])
  
  const handlePageClick = useCallback(async (pageId: string) => {
    if (pageId === currentPageId || isNavigating || isLoading || isSaving) {
      return
    }
    
    setIsNavigating(true)
    try {
      if (mode === 'preview') {
        router.push(`/pagtive/projects/${projectId}/preview#page-${pageId}`)
      } else {
        router.push(`/pagtive/projects/${projectId}/pages/${pageId}/edit`)
      }
    } catch (error) {
      console.error('Page navigation failed:', error)
    } finally {
      setIsNavigating(false)
    }
  }, [currentPageId, projectId, isNavigating, router, isLoading, isSaving, mode])
  
  const handleAddClick = async (insertIndex: number) => {
    if (isNavigating || isLoading || isSaving) return
    
    let prevPageId: string
    
    if (insertIndex === 0) {
      prevPageId = 'start'
    } else if (insertIndex > safePages.length) {
      prevPageId = 'end'
    } else {
      prevPageId = safePages[insertIndex - 1].id
    }
    
    setIsNavigating(true)
    try {
      router.push(`/pagtive/projects/${projectId}/pages/new?insertAfter=${prevPageId}`)
    } catch (error) {
      console.error('Navigation to add page failed:', error)
    } finally {
      setIsNavigating(false)
    }
  }
  
  const newPageIndex = getNewPageIndex()
  
  // Notify parent component of expand state change
  const handleExpandToggle = () => {
    setIsExpanded(!isExpanded)
    // If needed, can notify parent component to adjust layout via events
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent('pagtive-filmstrip-toggle', { 
        detail: { isExpanded: !isExpanded } 
      }))
    }
  }

  return (
    <div 
      className={`fixed left-0 top-12 bottom-0 z-30 transition-all duration-300 ${
        isExpanded ? 'w-32' : 'w-12'
      }`}
    >
      <div className="h-full border-r flex flex-col" style={{ backgroundColor: 'var(--background)', borderColor: 'var(--border)' }}>
        {/* Expand/collapse button */}
        <button
          onClick={handleExpandToggle}
          className="w-full h-10 flex items-center justify-center transition-colors hover:bg-[var(--secondary-hover)]" style={{ color: 'var(--foreground)' }}
          title={isExpanded ? 'Collapse' : 'Expand'}
        >
          {isExpanded ? (
            <ChevronDoubleLeftIcon className="w-4 h-4" />
          ) : (
            <ChevronDoubleRightIcon className="w-4 h-4" />
          )}
        </button>
        
        {/* Page list */}
        <div className="flex-1 overflow-y-auto p-2">
          <div className="space-y-2">
            {/* Add button at the beginning */}
            {isExpanded && (
              <button
                onClick={() => handleAddClick(0)}
                disabled={isLoading || isSaving || isNavigating}
                className="w-full h-6 flex items-center justify-center rounded transition-colors disabled:opacity-50 hover:bg-[var(--secondary-hover)]" style={{ color: 'var(--foreground)' }}
                title="Add page at the beginning"
              >
                <PlusIcon className="w-3 h-3" />
              </button>
            )}
            
            {safePages.map((page, index) => {
              const isCurrentPage = page.id === currentPageId
              const isBeforeNewPage = isAddPage && newPageIndex !== -1 && index === newPageIndex
              
              return (
                <div key={page.id}>
                  {/* If this is the new page insertion position, show placeholder */}
                  {isBeforeNewPage && (
                    <div className={`${isExpanded ? 'w-full h-16' : 'w-8 h-8 mx-auto'} mb-2`}>
                      <div className="w-full h-full border-2 border-dashed rounded-lg flex items-center justify-center" style={{ borderColor: 'var(--accent)' }}>
                        {isExpanded && (
                          <span className="text-xs" style={{ color: 'var(--foreground)', opacity: 0.7 }}>New Page</span>
                        )}
                      </div>
                    </div>
                  )}
                  
                  {/* Page card */}
                  <button
                    onClick={() => handlePageClick(page.id)}
                    disabled={isLoading || isSaving || isNavigating}
                    className={`
                      ${isExpanded ? 'w-full h-16' : 'w-8 h-8 mx-auto'}
                      relative rounded-lg transition-all
                      ${isCurrentPage 
                        ? 'border-2' 
                        : 'border'
                      }
                      disabled:opacity-50 disabled:cursor-not-allowed
                    `}
                    style={{
                      backgroundColor: isCurrentPage ? 'var(--accent)' : 'var(--code-bg)',
                      borderColor: isCurrentPage ? 'var(--foreground)' : 'var(--border)'
                    }}
                    title={page.title || `Page ${page.id}`}
                  >
                    {isExpanded ? (
                      <div className="p-2 text-left">
                        <div className="text-xs font-medium truncate" style={{ color: 'var(--foreground)' }}>
                          {page.title || `Page ${page.id}`}
                        </div>
                        <div className="text-xs opacity-50" style={{ color: 'var(--foreground)' }}>
                          #{index + 1}
                        </div>
                      </div>
                    ) : (
                      <span className="text-xs font-medium" style={{ color: 'var(--foreground)' }}>
                        {index + 1}
                      </span>
                    )}
                  </button>
                  
                  {/* Add button between pages */}
                  {isExpanded && (
                    <button
                      onClick={() => handleAddClick(index + 1)}
                      disabled={isLoading || isSaving || isNavigating}
                      className="w-full h-6 flex items-center justify-center rounded transition-colors disabled:opacity-50 hover:bg-[var(--secondary-hover)]" style={{ color: 'var(--foreground)' }}
                      title={`Add page after "${page.title}"`}
                    >
                      <PlusIcon className="w-3 h-3" />
                    </button>
                  )}
                </div>
              )
            })}
            
            {/* If new page is at the end, show placeholder (excluding no pages case) */}
            {isAddPage && newPageIndex === safePages.length && safePages.length > 0 && (
              <div className={`${isExpanded ? 'w-full h-16' : 'w-8 h-8 mx-auto'}`}>
                <div className="w-full h-full border-2 border-dashed rounded-lg flex items-center justify-center" style={{ borderColor: 'var(--accent)' }}>
                  {isExpanded && (
                    <span className="text-xs" style={{ color: 'var(--foreground)', opacity: 0.7 }}>New Page</span>
                  )}
                </div>
              </div>
            )}
            
            {/* If no pages, show empty state */}
            {safePages.length === 0 && isAddPage && (
              <div className={`${isExpanded ? 'w-full h-16' : 'w-8 h-8 mx-auto'}`}>
                <div className="w-full h-full border-2 border-dashed rounded-lg flex items-center justify-center" style={{ borderColor: 'var(--accent)' }}>
                  {isExpanded && (
                    <span className="text-xs" style={{ color: 'var(--foreground)', opacity: 0.7 }}>New Page</span>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}