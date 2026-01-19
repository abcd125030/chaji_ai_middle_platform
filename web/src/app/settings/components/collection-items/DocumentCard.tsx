'use client';

import React from 'react';
import { DocumentTextIcon, DocumentIcon, CodeBracketIcon, TrashIcon } from '@heroicons/react/24/outline';

interface DocumentCardProps {
  id: string;
  name: string;
  type: 'docx' | 'doc' | 'pdf' | 'txt' | 'md';
  size: number;
  uploadedAt: string;
  preview?: string;
  onDelete: (id: string) => void;
}

const DocumentCard: React.FC<DocumentCardProps> = ({
  id,
  name,
  type,
  size,
  uploadedAt,
  preview,
  onDelete
}) => {
  const getIcon = () => {
    const className = "h-6 w-6 text-[var(--foreground)]";
    switch(type) {
      case 'pdf':
        return <DocumentIcon className={className} />;
      case 'md':
        return <CodeBracketIcon className={className} />;
      default:
        return <DocumentTextIcon className={className} />;
    }
  };

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
        className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 p-1.5 bg-[var(--background)] rounded-lg text-[var(--muted-foreground)] hover:text-red-500 transition-all"
      >
        <TrashIcon className="h-3.5 w-3.5" />
      </button>
      
      <div className="flex items-start space-x-3">
        {/* Icon */}
        <div className="flex-shrink-0">
          {getIcon()}
        </div>
        
        {/* Content */}
        <div className="flex-1 min-w-0">
          <h3 className="text-sm font-medium text-[var(--foreground)] truncate mb-1">
            {name}
          </h3>
          
          {preview && (
            <p className="text-xs text-[var(--muted-foreground)] line-clamp-2 mb-2">
              {preview}
            </p>
          )}
          
          <div className="flex items-center space-x-3 text-[10px] text-[var(--muted-foreground)]">
            <span className="uppercase font-medium">{type}</span>
            <span>•</span>
            <span>{formatFileSize(size)}</span>
            <span>•</span>
            <span>{new Date(uploadedAt).toLocaleDateString()}</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default DocumentCard;