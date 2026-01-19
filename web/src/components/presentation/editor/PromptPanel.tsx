'use client'

import { ChevronDownIcon } from '@heroicons/react/24/outline'

interface PromptPanelProps {
  mode: 'add' | 'edit'
  isOpen: boolean
  prompt: string
  isLoading: boolean
  onClose: () => void
  onPromptChange: (value: string) => void
}

export function PromptPanel({
  mode,
  isOpen,
  prompt,
  isLoading,
  onClose,
  onPromptChange,
}: PromptPanelProps) {
  if (!isOpen) return null

  return (
    <div className="fixed bottom-20 left-1/2 -translate-x-1/2 z-40" style={{ width: '480px' }}>
      <div className="rounded-2xl shadow-xl border p-4" style={{ 
        backgroundColor: '#1a1a1a', 
        borderColor: '#2a2a2a',
        backdropFilter: 'blur(10px)'
      }}>
        {/* Title bar */}
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-lg font-semibold" style={{ color: '#ffffff' }}>
            {mode === 'add' ? 'Describe the content you want' : 'Describe the changes you want to make'}
          </h3>
          <button
            onClick={onClose}
            className="p-1 rounded-lg hover:bg-white/10"
            disabled={isLoading}
          >
            <ChevronDownIcon className="w-5 h-5" style={{ color: '#ffffff' }} />
          </button>
        </div>

        {/* Hint text */}
        <p className="text-sm mb-3" style={{ color: '#9ca3af' }}>
          When you upload content images, {'{image_name}'} will be automatically added for you. This symbol helps you specify the usage of that image in your prompt.
        </p>

        {/* Input field */}
        <textarea
          value={prompt}
          onChange={(e) => onPromptChange(e.target.value)}
          placeholder={mode === 'add' ? 'For example: Create a modern-style product showcase page...' : 'For example: Change the title to a larger font...'}
          disabled={isLoading}
          className="w-full h-32 px-3 py-2 rounded-lg border
                   focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent
                   disabled:opacity-50 disabled:cursor-not-allowed resize-none"
          style={{
            backgroundColor: '#0a0a0a',
            borderColor: '#2a2a2a',
            color: '#ffffff'
          }}
        />
      </div>
    </div>
  )
}