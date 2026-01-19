'use client';

import React from 'react';
import Image from 'next/image';
import { GlobeAltIcon, TrashIcon } from '@heroicons/react/24/outline';

interface WebUrlCardProps {
  id: string;
  title: string;
  url: string;
  excerpt: string;
  favicon?: string;
  addedAt: string;
  onDelete: (id: string) => void;
}

const WebUrlCard: React.FC<WebUrlCardProps> = ({
  id,
  title,
  url,
  excerpt,
  favicon,
  addedAt,
  onDelete
}) => {
  const domain = new URL(url).hostname.replace('www.', '');
  
  return (
    <div className="group relative bg-[var(--accent)] rounded-xl p-4 hover:shadow-lg transition-all duration-300">
      {/* Delete button */}
      <button
        onClick={() => onDelete(id)}
        className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 p-1.5 bg-[var(--background)] rounded-lg text-[var(--muted-foreground)] hover:text-red-500 transition-all"
      >
        <TrashIcon className="h-4 w-4" />
      </button>
      
      {/* Card content */}
      <div className="flex items-start space-x-3">
        {/* Favicon or default icon */}
        <div className="flex-shrink-0 w-8 h-8 bg-[var(--background)] rounded-lg flex items-center justify-center relative">
          {favicon ? (
            <Image src={favicon} alt="" width={20} height={20} />
          ) : (
            <GlobeAltIcon className="h-5 w-5 text-[var(--foreground)] opacity-70" />
          )}
        </div>
        
        {/* Text content */}
        <div className="flex-1 min-w-0">
          {/* Title */}
          <h3 className="text-xs font-semibold text-[var(--foreground)] truncate mb-1">
            {title || 'Untitled Page'}
          </h3>
          
          {/* Domain */}
          <p className="text-[10px] text-[var(--foreground)] opacity-70 mb-2">
            {domain}
          </p>
          
          {/* Excerpt */}
          <p className="text-[10px] text-[var(--muted-foreground)] leading-relaxed line-clamp-3">
            {excerpt || 'No description available'}
          </p>
          
          {/* Metadata */}
          <p className="text-[9px] text-[var(--muted-foreground)] opacity-60 mt-2">
            Added {new Date(addedAt).toLocaleDateString()}
          </p>
        </div>
      </div>
    </div>
  );
};

export default WebUrlCard;