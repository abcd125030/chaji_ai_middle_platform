'use client';

import React from 'react';
import Image from 'next/image';
import { PresentationChartBarIcon, TrashIcon } from '@heroicons/react/24/outline';

interface PresentationCardProps {
  id: string;
  name: string;
  type: 'pptx' | 'ppt';
  size: number;
  slides?: number;
  thumbnail?: string;
  uploadedAt: string;
  onDelete: (id: string) => void;
}

const PresentationCard: React.FC<PresentationCardProps> = ({
  id,
  name,
  type,
  size,
  slides,
  thumbnail,
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
    <div className="group relative bg-[var(--accent)] border border-[var(--border)] rounded-xl overflow-hidden hover:shadow-lg transition-all duration-300">
      {/* Delete button */}
      <button
        onClick={() => onDelete(id)}
        className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 p-1.5 bg-[var(--background)] rounded-lg text-[var(--muted-foreground)] hover:text-red-500 transition-all z-10"
      >
        <TrashIcon className="h-3.5 w-3.5" />
      </button>
      
      {/* Slide preview area */}
      <div className="relative h-24 bg-[var(--background)] border-b border-[var(--border)]">
        {thumbnail ? (
          <Image
            src={thumbnail}
            alt=""
            fill
            className="object-cover"
          />
        ) : (
          <div className="flex items-center justify-center h-full">
            {/* Slide mockup */}
            <div className="relative">
              <div className="w-16 h-12 bg-[var(--accent)] rounded shadow-lg flex items-center justify-center">
                <PresentationChartBarIcon className="h-6 w-6 text-[var(--foreground)]" />
              </div>
              {/* Additional slide hints */}
              <div className="absolute -right-1 -bottom-1 w-16 h-12 bg-[var(--accent)] opacity-60 rounded shadow-md -z-10"></div>
              <div className="absolute -right-2 -bottom-2 w-16 h-12 bg-[var(--accent)] opacity-30 rounded shadow -z-20"></div>
            </div>
          </div>
        )}
        
        {/* Slide counter badge */}
        {slides && (
          <div className="absolute bottom-2 right-2 px-2 py-1 bg-[var(--foreground)] text-[var(--background)] text-[10px] font-bold rounded-full">
            {slides} slides
          </div>
        )}
      </div>
      
      {/* Content area */}
      <div className="p-3">
        <h3 className="text-sm font-semibold text-[var(--foreground)] truncate mb-2">
          {name}
        </h3>
        
        <div className="flex items-center justify-between text-[10px] text-[var(--muted-foreground)]">
          <div className="flex items-center space-x-2">
            <span className="uppercase font-medium">
              {type}
            </span>
            <span>•</span>
            <span>{formatFileSize(size)}</span>
          </div>
          <span>{new Date(uploadedAt).toLocaleDateString()}</span>
        </div>
      </div>
    </div>
  );
};

export default PresentationCard;