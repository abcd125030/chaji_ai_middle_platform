'use client';

import React from 'react';
import { TableCellsIcon, TrashIcon } from '@heroicons/react/24/outline';

interface SpreadsheetCardProps {
  id: string;
  name: string;
  type: 'xlsx' | 'xls' | 'csv';
  size: number;
  rows?: number;
  columns?: number;
  sheets?: number;
  uploadedAt: string;
  onDelete: (id: string) => void;
}

const SpreadsheetCard: React.FC<SpreadsheetCardProps> = ({
  id,
  name,
  type,
  size,
  rows,
  columns,
  sheets,
  uploadedAt,
  onDelete
}) => {
  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };


  return (
    <div className="group relative bg-[var(--accent)] rounded-xl p-4 hover:shadow-lg transition-all duration-300">
      {/* Delete button */}
      <button
        onClick={() => onDelete(id)}
        className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 p-1.5 bg-[var(--background)] rounded-lg text-[var(--muted-foreground)] hover:text-red-500 transition-all z-10"
      >
        <TrashIcon className="h-3.5 w-3.5" />
      </button>
      
      <div className="flex items-start space-x-3">
        {/* Icon */}
        <div className="flex-shrink-0">
          <TableCellsIcon className="h-6 w-6 text-[var(--foreground)]" />
        </div>
          
        {/* Content */}
        <div className="flex-1 min-w-0">
          <h3 className="text-sm font-medium text-[var(--foreground)] truncate mb-2">
            {name}
          </h3>
          
          {/* Grid preview visualization */}
          <div className="bg-[var(--background)] rounded border border-[var(--border)] p-1.5 mb-2">
            <div className="grid grid-cols-5 gap-0.5 max-w-[120px]">
              {Array.from({ length: 15 }).map((_, i) => (
                <div
                  key={i}
                  className={`h-1.5 ${i < 5 ? 'bg-[var(--foreground)] opacity-60' : 'bg-[var(--muted-foreground)] opacity-30'} rounded-sm`}
                />
              ))}
            </div>
          </div>
          
          {/* Metadata */}
          <div className="space-y-1">
            {(rows || columns || sheets) && (
              <p className="text-[10px] text-[var(--muted-foreground)]">
                {rows && `${rows.toLocaleString()} rows`}
                {rows && columns && ' × '}
                {columns && `${columns} columns`}
                {sheets && sheets > 1 && ` • ${sheets} sheets`}
              </p>
            )}
            
            <div className="flex items-center space-x-2 text-[10px] text-[var(--muted-foreground)]">
              <span className="uppercase font-medium">
                {type}
              </span>
              <span>•</span>
              <span>{formatFileSize(size)}</span>
              <span>•</span>
              <span>{new Date(uploadedAt).toLocaleDateString()}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SpreadsheetCard;