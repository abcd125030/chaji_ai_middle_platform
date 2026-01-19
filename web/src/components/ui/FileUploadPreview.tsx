'use client';

import React from 'react';
import {
  DocumentTextIcon,
  XMarkIcon,
  PaperClipIcon,
  PhotoIcon,
} from '@heroicons/react/24/outline';

interface FileRecord {
  id: string;
  name: string;
  type: string;
  size: number;
  data: string;
}

interface FileUploadPreviewProps {
  uploadedFiles: FileRecord[];
  totalUploadSize: number;
  onFileDelete: (id: string) => void;
}

/**
 * File upload preview component - Display list of uploaded files
 * Supports file deletion and file information display
 */
const FileUploadPreview: React.FC<FileUploadPreviewProps> = ({
  uploadedFiles,
  totalUploadSize,
  onFileDelete,
}) => {
  /**
   * Get corresponding icon component based on file type
   * @param fileType File MIME type
   * @returns Corresponding icon component
   */
  const getFileIcon = (fileType: string) => {
    if (fileType.startsWith('image/')) {
      return <PhotoIcon className="h-5 w-5 text-[var(--foreground)] opacity-60" />;
    }
    switch (fileType) {
      case 'application/pdf':
        return <DocumentTextIcon className="h-5 w-5 text-[var(--foreground)] opacity-80" />;
      case 'text/markdown':
      case 'text/plain':
        return <DocumentTextIcon className="h-5 w-5 text-[var(--foreground)] opacity-70" />;
      default:
        return <PaperClipIcon className="h-5 w-5 text-[var(--foreground)] opacity-50" />;
    }
  };

  // Don't render component if no files uploaded
  if (uploadedFiles.length === 0) {
    return null;
  }

  return (
    <div className="p-2 mb-2 border-b border-[var(--border)]">
      {/* File statistics */}
      <div className="flex justify-between items-center mb-2">
        <span className="text-xs text-[var(--foreground)] opacity-50">
          {uploadedFiles.length}/6 files · {(totalUploadSize / (1024 * 1024)).toFixed(2)}/200 MB
        </span>
      </div>
      
      {/* File list grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
        {uploadedFiles.map((file) => (
          <div 
            key={file.id} 
            className="group relative flex items-center bg-[var(--accent)] bg-opacity-60 rounded-lg p-2 text-sm hover:bg-[var(--secondary-hover)] transition-colors"
          >
            {/* File icon */}
            <div className="flex-shrink-0 mr-2">
              {getFileIcon(file.type)}
            </div>
            
            {/* File name */}
            <span
              className="truncate text-[var(--foreground)] flex-1"
              title={file.name}
            >
              {file.name}
            </span>
            
            {/* File delete button */}
            <button
              onClick={() => onFileDelete(file.id)}
              className="absolute top-1 right-1 p-0.5 bg-[var(--accent)] rounded-full text-[var(--foreground)] opacity-0 group-hover:opacity-100 transition-opacity hover:bg-red-600"
              aria-label={`Delete file ${file.name}`}
              title={`Delete file ${file.name}`}
            >
              <XMarkIcon className="h-3 w-3" />
            </button>
          </div>
        ))}
      </div>
      
      {/* File size warning */}
      {totalUploadSize > 180 * 1024 * 1024 && (
        <div className="mt-2 text-xs text-amber-400">
          ⚠️ Total file size approaching limit (200MB)
        </div>
      )}
    </div>
  );
};

export default FileUploadPreview;