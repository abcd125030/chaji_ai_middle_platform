'use client'

import { useState } from 'react'
import {
  ArrowLeftIcon,
  ArrowUturnLeftIcon,
  PlusCircleIcon,
  PhotoIcon,
  LinkIcon,
  DocumentPlusIcon,
  SparklesIcon,
  ClockIcon,
  ChevronUpIcon,
  BookmarkIcon,
  ArrowDownTrayIcon,
} from '@heroicons/react/24/outline'

interface FloatingToolbarProps {
  mode: 'add' | 'edit'
  isLoading: boolean
  isSaving: boolean
  prompt: string
  hasContent?: boolean
  onPromptToggle: () => void
  onImageUpload: () => void
  onExternalLink: () => void
  onAddReference: () => void
  onGenerate: () => void
  onSave: () => void
  onUndo?: () => void
  onBack?: () => void
  onHistoryToggle?: () => void
}

export function FloatingToolbar({
  mode,
  isLoading,
  isSaving,
  prompt,
  hasContent,
  onPromptToggle,
  onImageUpload,
  onExternalLink,
  onAddReference,
  onGenerate,
  onSave,
  onUndo,
  onBack,
  onHistoryToggle,
}: FloatingToolbarProps) {
  const [showAddMenu, setShowAddMenu] = useState(false)

  const buttonClass = "w-9 h-9 rounded-lg flex items-center justify-center transition-all disabled:opacity-50 disabled:cursor-not-allowed hover:bg-white/10" 

  return (
    <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-50 flex flex-col items-center gap-2">
      {/* Main toolbar - using fixed dark theme styles to avoid being affected by iframe content */}
      <div className="rounded-2xl shadow-lg border px-6 py-2 flex items-center justify-between" style={{ 
        backgroundColor: '#1a1a1a', 
        borderColor: '#2a2a2a',
        backdropFilter: 'blur(10px)',
        width: '480px'
      }}>
        {/* All buttons evenly distributed */}
        {onBack && (
          <button
            onClick={onBack}
            className={buttonClass}
            style={{ color: '#ffffff' }}
            disabled={isLoading || isSaving}
            title="Back"
          >
            <ArrowLeftIcon className="w-5 h-5" />
          </button>
        )}
        
        {mode === 'edit' && onUndo && hasContent && (
          <button
            onClick={onUndo}
            className={buttonClass}
            style={{ color: '#ffffff' }}
            disabled={isLoading || isSaving}
            title="Undo"
          >
            <ArrowUturnLeftIcon className="w-5 h-5" />
          </button>
        )}

        {/* Add content button */}
        <div className="relative">
          <button
            onClick={() => setShowAddMenu(!showAddMenu)}
            className={buttonClass}
            style={{ color: '#ffffff' }}
            disabled={isLoading || isSaving}
            title="Add content"
          >
            <PlusCircleIcon className="w-5 h-5" />
          </button>

          {/* Add content menu */}
          {showAddMenu && (
            <div className="absolute bottom-10 left-0 rounded-lg shadow-lg border py-1 min-w-[200px]" style={{ 
              backgroundColor: '#1a1a1a', 
              borderColor: '#2a2a2a',
              backdropFilter: 'blur(10px)'
            }}>
              <button
                onClick={() => {
                  onImageUpload()
                  setShowAddMenu(false)
                }}
                className="w-full px-3 py-2 flex items-center gap-2 text-left text-sm hover:opacity-70"
              >
                <PhotoIcon className="w-4 h-4" />
                <span>Upload Image</span>
              </button>
              <button
                onClick={() => {
                  onExternalLink()
                  setShowAddMenu(false)
                }}
                className="w-full px-3 py-2 flex items-center gap-2 text-left text-sm hover:opacity-70"
              >
                <LinkIcon className="w-4 h-4" />
                <span>External Link</span>
              </button>
              <button
                onClick={() => {
                  onAddReference()
                  setShowAddMenu(false)
                }}
                className="w-full px-3 py-2 flex items-center gap-2 text-left text-sm hover:opacity-70"
              >
                <DocumentPlusIcon className="w-4 h-4" />
                <span>Add Reference Page</span>
              </button>
              <div className="h-px my-1" style={{ backgroundColor: '#2a2a2a' }} />
              <button
                onClick={() => {
                  onImageUpload()
                  setShowAddMenu(false)
                }}
                className="w-full px-3 py-2 flex items-center gap-2 text-left text-sm hover:opacity-70"
              >
                <BookmarkIcon className="w-4 h-4" />
                <span>Reference Image</span>
              </button>
            </div>
          )}
        </div>

        {/* Prompt input button */}
        <button
          onClick={onPromptToggle}
          className={buttonClass}
          style={{ 
            backgroundColor: prompt ? '#383838' : 'transparent',
            color: '#ffffff'
          }}
          disabled={isLoading || isSaving}
          title="Edit prompt"
        >
          <ChevronUpIcon className="w-5 h-5" />
        </button>

        {/* History button (edit mode only) */}
        {mode === 'edit' && onHistoryToggle && (
          <button
            onClick={onHistoryToggle}
            className={buttonClass}
            style={{ color: '#ffffff' }}
            disabled={isLoading || isSaving}
            title="History"
          >
            <ClockIcon className="w-5 h-5" />
          </button>
        )}

        {/* Generate button */}
        <button
          onClick={onGenerate}
          className={`${buttonClass} ${isLoading ? 'animate-pulse' : ''}`}
          style={{ 
            backgroundColor: '#383838', 
            color: '#ffffff' 
          }}
          disabled={isLoading || !prompt.trim()}
          title={mode === 'add' ? 'Generate' : 'Apply Changes'}
        >
          <SparklesIcon className="w-5 h-5" />
        </button>
        
        {/* Save button */}
        <button
          onClick={onSave}
          className={`${buttonClass} ${isSaving ? 'animate-pulse' : ''}`}
          style={{ 
            backgroundColor: '#383838', 
            color: '#ffffff',
            opacity: isSaving || isLoading || (mode === 'add' && !hasContent) ? 0.5 : 1
          }}
          disabled={isSaving || isLoading || (mode === 'add' && !hasContent)}
          title="Save"
        >
          <ArrowDownTrayIcon className="w-5 h-5" />
        </button>
      </div>

      {/* Click outside to close menu */}
      {showAddMenu && (
        <div
          className="fixed inset-0 z-40"
          onClick={() => setShowAddMenu(false)}
        />
      )}
    </div>
  )
}