'use client'

import Image from 'next/image'
import { XMarkIcon, ChevronUpIcon, ChevronDownIcon } from '@heroicons/react/24/outline'

interface ReferenceContent {
  pageId: string
  pageName: string
  includeHtml: boolean
  includeCss: boolean
  includeJs: boolean
}

interface ImageInfo {
  id: string
  url: string
  filename: string
  isReference?: boolean
}

interface ReferencePanelProps {
  references: ReferenceContent[]
  images: ImageInfo[]
  isOpen: boolean
  isLoading: boolean
  onToggle: () => void
  onRemoveReference: (pageId: string) => void
  onRemoveImage: (id: string) => void
  onReferenceClick: (ref: ReferenceContent) => void
}

export function ReferencePanel({
  references,
  images,
  isOpen,
  isLoading,
  onToggle,
  onRemoveReference,
  onRemoveImage,
  onReferenceClick,
}: ReferencePanelProps) {
  const hasContent = references.length > 0 || images.length > 0

  if (!hasContent) return null

  return (
    <div className="fixed bottom-20 left-1/2 -translate-x-1/2 z-30" style={{ width: '480px' }}>
      <div className="rounded-2xl shadow-xl border" style={{ 
        backgroundColor: '#1a1a1a', 
        borderColor: '#2a2a2a',
        backdropFilter: 'blur(10px)'
      }}>
        {/* 折叠标题栏 */}
        <button
          onClick={onToggle}
          disabled={isLoading}
          className="w-full px-4 py-3 flex items-center justify-between rounded-t-2xl transition-colors hover:bg-white/10"
        >
          <span className="text-sm font-medium" style={{ color: '#ffffff' }}>
            Reference Content ({references.length + images.length})
          </span>
          {isOpen ? (
            <ChevronDownIcon className="w-4 h-4" style={{ color: '#ffffff', opacity: 0.5 }} />
          ) : (
            <ChevronUpIcon className="w-4 h-4" style={{ color: '#ffffff', opacity: 0.5 }} />
          )}
        </button>

        {/* 内容区域 */}
        {isOpen && (
          <div className="px-4 pb-4 max-h-60 overflow-y-auto">
            {/* 参考页面 */}
            {references.length > 0 && (
              <div className="mb-3">
                <h4 className="text-xs font-medium mb-2" style={{ color: '#ffffff', opacity: 0.5 }}>Reference Pages</h4>
                <div className="space-y-2">
                  {references.map((ref) => (
                    <div
                      key={ref.pageId}
                      className="p-2 rounded-lg" style={{ backgroundColor: '#0a0a0a' }}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-medium" style={{ color: '#ffffff' }}>
                          {ref.pageName}
                        </span>
                        <button
                          onClick={() => onRemoveReference(ref.pageId)}
                          className="p-1 rounded transition-colors hover:bg-white/10"
                        >
                          <XMarkIcon className="w-4 h-4" style={{ color: '#ffffff', opacity: 0.4 }} />
                        </button>
                      </div>
                      <div className="flex gap-3">
                        <label className="flex items-center text-xs cursor-pointer" style={{ color: '#ffffff', opacity: 0.7 }}>
                          <input
                            type="checkbox"
                            checked={ref.includeHtml}
                            onChange={() => onReferenceClick({ ...ref, includeHtml: !ref.includeHtml })}
                            className="mr-1.5 w-3 h-3"
                          />
                          HTML
                        </label>
                        <label className="flex items-center text-xs cursor-pointer" style={{ color: '#ffffff', opacity: 0.7 }}>
                          <input
                            type="checkbox"
                            checked={ref.includeCss}
                            onChange={() => onReferenceClick({ ...ref, includeCss: !ref.includeCss })}
                            className="mr-1.5 w-3 h-3"
                          />
                          CSS
                        </label>
                        <label className="flex items-center text-xs cursor-pointer" style={{ color: '#ffffff', opacity: 0.7 }}>
                          <input
                            type="checkbox"
                            checked={ref.includeJs}
                            onChange={() => onReferenceClick({ ...ref, includeJs: !ref.includeJs })}
                            className="mr-1.5 w-3 h-3"
                          />
                          JS
                        </label>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* 参考图片 */}
            {images.length > 0 && (
              <div>
                <h4 className="text-xs font-medium mb-2" style={{ color: '#ffffff', opacity: 0.5 }}>Reference Images</h4>
                <div className="flex flex-wrap gap-2">
                  {images.map((img) => (
                    <div
                      key={img.id}
                      className="relative group"
                    >
                      <Image
                        src={img.url}
                        alt={img.filename}
                        width={64}
                        height={64}
                        className="w-16 h-16 object-cover rounded-lg"
                      />
                      <button
                        onClick={() => onRemoveImage(img.id)}
                        className="absolute -top-1 -right-1 p-0.5 bg-red-500 text-white rounded-full opacity-0 group-hover:opacity-100 transition-opacity"
                      >
                        <XMarkIcon className="w-3 h-3" />
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}