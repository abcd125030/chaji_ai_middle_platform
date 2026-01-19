'use client';

import React, { useState, useRef } from 'react';
import { 
  CloudArrowUpIcon, 
  FolderOpenIcon,
} from '@heroicons/react/24/outline';
import toast from 'react-hot-toast';
import { WebUrlCard, DocumentCard, SpreadsheetCard, PresentationCard } from './collection-items';

interface CollectionFile {
  id: string;
  name: string;
  type: string;
  size: number;
  uploadedAt: string;
  // Additional fields for different types
  title?: string;
  url?: string;
  excerpt?: string;
  preview?: string;
  rows?: number;
  columns?: number;
  sheets?: number;
  slides?: number;
}

const CollectionsSection: React.FC = () => {
  const [collectionFiles, setCollectionFiles] = useState<CollectionFile[]>([
    // Sample data for demonstration - remove in production
    {
      id: '1',
      name: 'Sample Web Page',
      type: 'web',
      size: 0,
      uploadedAt: new Date().toISOString(),
      title: 'Understanding React Server Components',
      url: 'https://example.com/react-server-components',
      excerpt: 'React Server Components represent a new way to build React applications, allowing components to be rendered on the server and streamed to the client...'
    },
    {
      id: '2',
      name: 'Project Documentation.docx',
      type: 'docx',
      size: 245760,
      uploadedAt: new Date().toISOString(),
      preview: 'This document outlines the project requirements and specifications...'
    },
    {
      id: '3',
      name: 'Sales Report Q4.xlsx',
      type: 'xlsx',
      size: 524288,
      uploadedAt: new Date().toISOString(),
      rows: 1500,
      columns: 12,
      sheets: 3
    },
    {
      id: '4',
      name: 'Company Presentation.pptx',
      type: 'pptx',
      size: 2097152,
      uploadedAt: new Date().toISOString(),
      slides: 24
    }
  ]);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  
  // Handle file upload
  const handleFileUpload = (files: FileList | null) => {
    if (!files) return;
    
    const allowedTypes = ['docx', 'doc', 'xlsx', 'xls', 'csv', 'pptx', 'ppt', 'pdf', 'md', 'txt'];
    const validFiles: File[] = [];
    
    Array.from(files).forEach(file => {
      const fileExtension = file.name.split('.').pop()?.toLowerCase() || '';
      if (allowedTypes.includes(fileExtension)) {
        validFiles.push(file);
      } else {
        toast.error(`File type .${fileExtension} is not supported`);
      }
    });
    
    if (validFiles.length === 0) return;
    
    const newFiles = validFiles.map(file => ({
      id: Date.now().toString() + Math.random().toString(36).substr(2, 9),
      name: file.name,
      type: file.name.split('.').pop()?.toLowerCase() || 'unknown',
      size: file.size,
      uploadedAt: new Date().toISOString()
    }));
    
    setCollectionFiles([...collectionFiles, ...newFiles]);
    toast.success(`${validFiles.length} file(s) uploaded successfully`);
  };
  
  // Handle drag events
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };
  
  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };
  
  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    handleFileUpload(e.dataTransfer.files);
  };
  
  // Handle file deletion
  const handleFileDelete = (id: string) => {
    setCollectionFiles(collectionFiles.filter(file => file.id !== id));
    toast.success('File removed');
  };

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-semibold text-[var(--foreground)]">
        Collections
      </h2>
      
      {/* Upload Area */}
      <div 
        className={`bg-[var(--accent)] rounded-lg p-8 border-2 border-dashed transition-all ${
          isDragging ? 'border-purple-500 bg-purple-50/5' : 'border-transparent'
        }`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        <div className="text-center">
          <CloudArrowUpIcon className="h-12 w-12 text-[var(--muted-foreground)] mx-auto mb-4" />
          <h3 className="text-lg font-medium text-[var(--foreground)] mb-2">
            Upload Files
          </h3>
          <p className="text-sm text-[var(--muted-foreground)] mb-4">
            Drag and drop files here, or click to browse
          </p>
          <button
            onClick={() => fileInputRef.current?.click()}
            className="px-6 py-2.5 bg-[var(--foreground)] text-[var(--background)] rounded-full font-medium text-sm transition-all hover:scale-105 hover:shadow-[0_8px_16px_rgba(0,0,0,0.15)]"
          >
            Select Files
          </button>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            className="hidden"
            onChange={(e) => handleFileUpload(e.target.files)}
            accept=".docx,.xlsx,.pptx,.pdf,.md,.txt,.csv"
          />
          <p className="text-xs text-[var(--muted-foreground)] mt-4">
            Supported: DOCX, XLSX, PPT, PDF, MD, TXT, CSV
          </p>
        </div>
      </div>
      
      {/* Files List */}
      <div>
        {collectionFiles.length === 0 ? (
          <div className="bg-[var(--accent)] rounded-lg p-12 text-center">
            <FolderOpenIcon className="h-12 w-12 text-[var(--muted-foreground)] mx-auto mb-4" />
            <p className="text-[var(--muted-foreground)]">No files uploaded yet</p>
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-1 md:grid-cols-2 lg:grid-cols-2 xl:grid-cols-3">
            {collectionFiles.map((file) => {
              // Render different card types based on file type
              if (file.type === 'web') {
                return (
                  <WebUrlCard
                    key={file.id}
                    id={file.id}
                    title={file.title || ''}
                    url={file.url || ''}
                    excerpt={file.excerpt || ''}
                    addedAt={file.uploadedAt}
                    onDelete={handleFileDelete}
                  />
                );
              } else if (['docx', 'doc', 'pdf', 'txt', 'md'].includes(file.type)) {
                return (
                  <DocumentCard
                    key={file.id}
                    id={file.id}
                    name={file.name}
                    type={file.type as 'docx' | 'doc' | 'pdf' | 'txt' | 'md'}
                    size={file.size}
                    uploadedAt={file.uploadedAt}
                    preview={file.preview}
                    onDelete={handleFileDelete}
                  />
                );
              } else if (['xlsx', 'xls', 'csv'].includes(file.type)) {
                return (
                  <SpreadsheetCard
                    key={file.id}
                    id={file.id}
                    name={file.name}
                    type={file.type as 'xlsx' | 'xls' | 'csv'}
                    size={file.size}
                    rows={file.rows}
                    columns={file.columns}
                    sheets={file.sheets}
                    uploadedAt={file.uploadedAt}
                    onDelete={handleFileDelete}
                  />
                );
              } else if (['pptx', 'ppt'].includes(file.type)) {
                return (
                  <PresentationCard
                    key={file.id}
                    id={file.id}
                    name={file.name}
                    type={file.type as 'pptx' | 'ppt'}
                    size={file.size}
                    slides={file.slides}
                    uploadedAt={file.uploadedAt}
                    onDelete={handleFileDelete}
                  />
                );
              }
              return null;
            })}
          </div>
        )}
      </div>
    </div>
  );
};

export default CollectionsSection;