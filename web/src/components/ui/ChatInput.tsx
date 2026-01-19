'use client';

import React, { useState, useRef } from 'react';
import {
  MagnifyingGlassIcon,
  PaperClipIcon,
} from '@heroicons/react/24/outline';
import PaperPlane3D from '@/components/icons/PaperPlane3D';
import { toast } from 'react-hot-toast';
import { addFile } from '@/lib/db';
import FileUploadPreview from './FileUploadPreview';
import { 
  validateFiles, 
  isImageFile
} from './utils/file-validator';
import { 
  processImage, 
  extractFirstFrame, 
  needsSpecialProcessing,
  getImageDimensions,
  checkImageDimensions
} from './utils/image-processor';

interface FileRecord {
  id: string;
  name: string;
  type: string;
  size: number;
  data: string;
}

interface ChatInputProps {
  uploadedFiles: FileRecord[];
  setUploadedFiles: React.Dispatch<React.SetStateAction<FileRecord[]>>;
  totalUploadSize: number;
  setTotalUploadSize: React.Dispatch<React.SetStateAction<number>>;
  isLoading: boolean;
  sendShortcut: string;
  onSubmit: (message: string, activeMode: string | null) => void;
  onFileDelete: (id: string) => void;
  onDrop: (e: React.DragEvent) => void;
  onDragEnter: (e: React.DragEvent) => void;
  onDragLeave: (e: React.DragEvent) => void;
  isDragging: boolean;
}

/**
 * Chat input component - handles all user input
 * Including text input, file upload, function buttons, etc.
 */
const ChatInput: React.FC<ChatInputProps> = ({
  uploadedFiles,
  setUploadedFiles,
  totalUploadSize,
  setTotalUploadSize,
  isLoading,
  sendShortcut,
  onSubmit,
  onFileDelete,
  onDrop,
  onDragEnter,
  onDragLeave,
  isDragging,
}) => {
  const [inputValue, setInputValue] = useState('');
  const [activeButton, setActiveButton] = useState<string | null>(null);
  const [_uploadProgress, setUploadProgress] = useState<number>(0);
  const [_isProcessing, setIsProcessing] = useState<boolean>(false);
  const inputRef = useRef<HTMLTextAreaElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const lineHeight = 32;

  // Auto-adjust textarea height, max 8 lines
  const autoResizeTextarea = (_e: React.ChangeEvent<HTMLTextAreaElement> | React.FormEvent<HTMLTextAreaElement>) => {
    const textarea = inputRef.current;
    if (textarea) {
      textarea.style.height = 'auto';
      const maxHeight = lineHeight * 8;
      textarea.style.height = Math.min(textarea.scrollHeight, maxHeight) + 'px';
    }
  };

  // Handle message submission
  const handleSubmit = () => {
    if (!inputValue.trim() || isLoading) return;
    
    onSubmit(inputValue, activeButton);
    setInputValue('');
    setActiveButton(null);
    
    // Reset textarea height
    if (inputRef.current) {
      inputRef.current.style.height = `${lineHeight}px`;
    }
  };

  // Handle file selection
  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    if (files.length === 0) return;

    await handleFileUpload(files);
    
    // Reset file input
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  // Handle file upload logic
  const handleFileUpload = async (files: File[]) => {
    // 验证文件 - 将 FileRecord 转换为 File-like 对象用于验证
    const existingFilesForValidation = uploadedFiles.map(f => ({
      name: f.name,
      size: f.size,
      type: f.type
    })) as unknown as File[];
    const validation = validateFiles(files, existingFilesForValidation);
    
    if (!validation.valid) {
      validation.errors.forEach(error => toast.error(error));
      return;
    }

    setIsProcessing(true);
    setUploadProgress(0);
    const processedFiles: File[] = [];
    const totalFiles = validation.validFiles.length;
    let processedCount = 0;

    try {
      // 处理每个文件
      for (const file of validation.validFiles) {
        let processedFile = file;

        // 如果是图片文件，进行特殊处理
        if (isImageFile(file)) {
          // 检查是否需要特殊处理（GIF、HEIC等）
          if (needsSpecialProcessing(file)) {
            try {
              processedFile = await extractFirstFrame(file);
              toast(`已提取 ${file.name} 的第一帧`, { 
                icon: 'ℹ️',
                duration: 2000 
              });
            } catch (error) {
              console.error('提取第一帧失败:', error);
              toast.error(`处理 ${file.name} 失败`);
              continue;
            }
          }

          // 检查图片尺寸
          try {
            const dimensions = await getImageDimensions(processedFile);
            const dimensionCheck = checkImageDimensions(dimensions, 4096);
            
            if (!dimensionCheck.valid) {
              toast.error(dimensionCheck.error || '图片尺寸超限');
              continue;
            }

            // 如果尺寸大于1440或文件大于3MB，进行压缩
            const maxDimension = Math.max(dimensions.width, dimensions.height);
            if (maxDimension > 1440 || processedFile.size > 3 * 1024 * 1024) {
              processedFile = await processImage(processedFile, {
                maxWidth: 1440,
                maxHeight: 1440,
                maxSizeInBytes: 3 * 1024 * 1024,
                outputFormat: 'jpeg',
                quality: 0.9
              });
              toast(`已优化图片 ${file.name}`, { 
                icon: 'ℹ️',
                duration: 2000 
              });
            }
          } catch (error) {
            console.error('处理图片失败:', error);
            toast.error(`处理图片 ${file.name} 失败`);
            continue;
          }
        }

        processedFiles.push(processedFile);
        
        // 更新进度
        processedCount++;
        setUploadProgress((processedCount / totalFiles) * 50); // 处理占50%
      }

      if (processedFiles.length === 0) {
        setIsProcessing(false);
        setUploadProgress(0);
        return;
      }

      // 计算新的总大小
      const newTotalSize = processedFiles.reduce((sum, file) => sum + file.size, totalUploadSize);
      setTotalUploadSize(newTotalSize);

      // 转换为 Base64 并保存
      let uploadedCount = 0;
      const uploadPromises = processedFiles.map(async (file) => {
        // addFile 会自动将文件转换为 base64
        const result = await addFile(file);
        
        // 更新上传进度
        uploadedCount++;
        setUploadProgress(50 + (uploadedCount / processedFiles.length) * 50); // 上传占50%
        
        return result;
      });

      const newFiles = await Promise.all(uploadPromises);
      setUploadedFiles(prevFiles => [...prevFiles, ...newFiles]);
      
      toast.success(`成功上传 ${processedFiles.length} 个文件`);
      setUploadProgress(100);
      
      // 延迟重置进度
      setTimeout(() => {
        setIsProcessing(false);
        setUploadProgress(0);
      }, 500);
    } catch (error) {
      console.error('文件上传失败:', error);
      toast.error('文件上传失败');
      setIsProcessing(false);
      setUploadProgress(0);
    }
  };

  return (
    <div className="w-full max-w-3xl mx-auto">
      {/* File drop zone */}
      <div
        className={`rounded-lg p-2.5 shadow-sm border-2 border-dashed transition-all ${
          isDragging
            ? 'border-[var(--accent)] bg-[var(--card-bg)] bg-opacity-80'
            : 'border-transparent bg-[var(--card-bg)] bg-opacity-60'
        }`}
        onDragEnter={onDragEnter}
        onDragLeave={onDragLeave}
        onDragOver={(e) => e.preventDefault()}
        onDrop={onDrop}
      >
        {/* File preview component */}
        <FileUploadPreview
          uploadedFiles={uploadedFiles}
          totalUploadSize={totalUploadSize}
          onFileDelete={onFileDelete}
        />
        
        {/* Input area */}
        <div className="flex items-center">
          <textarea
            ref={inputRef}
            placeholder="Enter your question"
            className="flex-grow bg-transparent border-0 focus:ring-0 outline-none text-[0.8rem] text-[var(--foreground)] placeholder:text-[var(--foreground)] placeholder-opacity-50 resize-none transition-all duration-200"
            value={inputValue}
            rows={1}
            style={{ 
              maxHeight: `${lineHeight * 8}px`, 
              minHeight: `${lineHeight}px`, 
              overflowY: 'auto' 
            }}
            onChange={(e) => {
              setInputValue(e.target.value);
              autoResizeTextarea(e);
            }}
            onInput={autoResizeTextarea}
            onKeyDown={(e) => {
              if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
                handleSubmit();
              }
            }}
            disabled={isLoading}
          />
        </div>
        
        {/* Bottom action buttons area */}
        <div className="mt-2 flex items-center justify-between">
          <div className="flex items-center space-x-2">
            {/* File upload button (PaperClipIcon) */}
            <label className="p-2 text-[var(--foreground)] opacity-70 hover:opacity-100 transition-colors cursor-pointer">
              <PaperClipIcon className="h-6 w-6" />
              <input
                ref={fileInputRef}
                type="file"
                multiple
                className="hidden"
                onChange={handleFileSelect}
                accept=".docx,.xlsx,.ppt,.pdf,.md,.txt,.json,.jpg,.jpeg,.png,.webp"
                tabIndex={-1}
              />
            </label>

            {/* Deep Research button */}
            <button
              className={`flex items-center space-x-1.5 text-sm py-1.5 px-3 rounded-full transition-colors cursor-pointer ${
                activeButton === 'research'
                  ? 'bg-[var(--foreground)] text-[var(--background)]'
                  : 'text-[var(--foreground)] opacity-70 hover:bg-[var(--secondary-hover)] hover:opacity-100'
              }`}
              title="Suitable for deep search and research"
              aria-label="Suitable for deep search and research"
              onClick={() => setActiveButton(activeButton === 'research' ? null : 'research')}
              disabled={isLoading}
            >
              <MagnifyingGlassIcon className="h-4 w-4 sm:hidden mx-auto" />
              <span className="hidden sm:inline">Deep Research</span>
            </button>
          </div>

          {/* Send button */}
          <button
            className="p-2 text-[var(--foreground)] opacity-70 hover:opacity-100 transition-colors cursor-pointer"
            title="Send message"
            aria-label="Send message"
            disabled={isLoading}
            onClick={handleSubmit}
          >
            <PaperPlane3D className="h-6 w-6" />
          </button>
        </div>
      </div>
      
      {/* Keyboard shortcut hint */}
      <div className="text-xs text-[var(--foreground)] opacity-50 pr-2.5 text-right mt-2">
        {sendShortcut} to send
      </div>
    </div>
  );
};

export default ChatInput;