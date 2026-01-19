'use client';

import { BookOpenIcon, AcademicCapIcon } from '@heroicons/react/24/outline';

export type ViewMode = 'observation' | 'training';

interface ModeToggleProps {
  mode: ViewMode;
  onModeChange: (mode: ViewMode) => void;
}

export function ModeToggle({ mode, onModeChange }: ModeToggleProps) {
  return (
    <div className="inline-flex items-center gap-2 p-1 bg-slate-800/50 rounded-lg border border-slate-700">
      <button
        onClick={() => onModeChange('observation')}
        className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-all ${
          mode === 'observation'
            ? 'bg-cyan-500/20 text-cyan-300 shadow-sm'
            : 'text-slate-400 hover:text-slate-200 hover:bg-slate-700/50'
        }`}
      >
        <BookOpenIcon className="w-4 h-4" />
        故事模式
      </button>
      <button
        onClick={() => onModeChange('training')}
        className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-all ${
          mode === 'training'
            ? 'bg-purple-500/20 text-purple-300 shadow-sm'
            : 'text-slate-400 hover:text-slate-200 hover:bg-slate-700/50'
        }`}
      >
        <AcademicCapIcon className="w-4 h-4" />
        培训模式
      </button>
    </div>
  );
}
