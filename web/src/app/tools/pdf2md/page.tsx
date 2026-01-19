'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { authFetch, isAuthenticated } from '@/lib/auth-fetch';
import toast from 'react-hot-toast';
import {
  DocumentTextIcon,
  CloudArrowUpIcon,
  XMarkIcon,
  LanguageIcon,
  DocumentDuplicateIcon
} from '@heroicons/react/24/outline';

interface UploadedFile {
  name: string;
  size: number;
  data: string; // base64
  translate?: boolean; // 是否翻译
  targetLanguage?: 'zh' | 'en'; // 目标语言
  pageRangeStart?: number; // 起始页码
  pageRangeEnd?: number; // 结束页码
}

/**
 * PDF上传页面
 * 允许用户上传多个PDF文件进行解析
 */
export default function PDF2MDUploadPage() {
  const router = useRouter();
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [isDragging, setIsDragging] = useState(false);

  /**
   * 检查登录状态
   */
  useEffect(() => {
    if (!isAuthenticated()) {
      // 保存当前路径用于登录后回调
      const currentPath = window.location.pathname + window.location.search;
      const callbackUrl = encodeURIComponent(currentPath);
      const basePath = process.env.NEXT_PUBLIC_BASE_PATH || '';

      // 跳转到登录页
      window.location.href = `${basePath}/auth/login?callbackUrl=${callbackUrl}`;
    }
  }, []);

  /**
   * 处理文件选择
   */
  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = Array.from(e.target.files || []);
    await processFiles(selectedFiles);
  };

  /**
   * 处理拖拽事件
   */
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);

    const droppedFiles = Array.from(e.dataTransfer.files);
    await processFiles(droppedFiles);
  };

  /**
   * 处理文件（验证+转换base64）
   */
  const processFiles = async (fileList: File[]) => {
    // 只接受PDF文件
    const pdfFiles = fileList.filter(file =>
      file.type === 'application/pdf' || file.name.endsWith('.pdf')
    );

    if (pdfFiles.length === 0) {
      toast.error('请上传PDF格式的文件');
      return;
    }

    // 检查文件数量限制
    if (files.length + pdfFiles.length > 10) {
      toast.error('最多只能上传10个PDF文件');
      return;
    }

    // 检查单个文件大小（80MB限制）
    const oversizedFiles = pdfFiles.filter(file => file.size > 80 * 1024 * 1024);
    if (oversizedFiles.length > 0) {
      toast.error(`文件 ${oversizedFiles[0].name} 超过80MB限制`);
      return;
    }

    // 转换为base64
    const uploadedFiles: UploadedFile[] = await Promise.all(
      pdfFiles.map(async file => {
        const base64 = await fileToBase64(file);
        return {
          name: file.name,
          size: file.size,
          data: base64,
          translate: false, // 默认不翻译
          targetLanguage: 'zh', // 默认中文
          pageRangeStart: undefined, // 默认全部页面
          pageRangeEnd: undefined
        };
      })
    );

    setFiles(prev => [...prev, ...uploadedFiles]);
    toast.success(`添加了 ${uploadedFiles.length} 个文件`);
  };

  /**
   * 文件转base64
   */
  const fileToBase64 = (file: File): Promise<string> => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => {
        const result = reader.result as string;
        // 移除data:application/pdf;base64,前缀
        const base64 = result.split(',')[1];
        resolve(base64);
      };
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
  };

  /**
   * 移除文件
   */
  const handleRemoveFile = (index: number) => {
    setFiles(prev => prev.filter((_, i) => i !== index));
  };

  /**
   * 更新文件的翻译设置
   */
  const handleTranslateToggle = (index: number, translate: boolean) => {
    setFiles(prev => prev.map((file, i) =>
      i === index ? { ...file, translate } : file
    ));
  };

  /**
   * 更新文件的目标语言
   */
  const handleTargetLanguageChange = (index: number, targetLanguage: 'zh' | 'en') => {
    setFiles(prev => prev.map((file, i) =>
      i === index ? { ...file, targetLanguage } : file
    ));
  };

  /**
   * 更新文件的页码范围
   */
  const handlePageRangeChange = (
    index: number,
    type: 'start' | 'end',
    value: string
  ) => {
    const numValue = value === '' ? undefined : parseInt(value);
    setFiles(prev => prev.map((file, i) => {
      if (i !== index) return file;
      if (type === 'start') {
        return { ...file, pageRangeStart: numValue };
      } else {
        return { ...file, pageRangeEnd: numValue };
      }
    }));
  };

  /**
   * 提交上传
   */
  const handleUpload = async () => {
    if (files.length === 0) {
      toast.error('请先选择要上传的PDF文件');
      return;
    }

    setIsUploading(true);
    try {
      const response = await authFetch('/api/webapps/toolkit/extractor/upload/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          files: files.map(f => ({
            filename: f.name,
            data: f.data,
            translate: f.translate || false,
            target_language: f.targetLanguage || 'zh',
            page_range_start: f.pageRangeStart,
            page_range_end: f.pageRangeEnd
          }))
        })
      });

      const data = await response.json();

      if (data.status === 'success') {
        // 保存任务ID到localStorage
        const taskIds = data.data.task_ids || [];
        const existingTaskIds = localStorage.getItem('pdf2md_task_ids');
        const allTaskIds = existingTaskIds
          ? [...JSON.parse(existingTaskIds), ...taskIds]
          : taskIds;
        localStorage.setItem('pdf2md_task_ids', JSON.stringify(allTaskIds));

        toast.success(data.data.message);
        // 跳转到进度页面
        router.push('/tools/pdf2md/progress');
      } else {
        throw new Error(data.message || '上传失败');
      }
    } catch (error) {
      console.error('上传失败:', error);
      toast.error(error instanceof Error ? error.message : '上传失败，请重试');
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="min-h-screen bg-black">
      {/* 顶部导航栏 */}
      <div className="border-b border-[#1A1A1A] bg-[#0A0A0A]">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <DocumentTextIcon className="w-6 h-6 text-white" />
              <h1 className="text-xl font-semibold text-white">PDF转Markdown</h1>
            </div>
            <button
              onClick={() => router.push('/tools/pdf2md/progress')}
              className="px-4 py-2 bg-[#0A0A0A] text-[#EDEDED] rounded-lg border border-[#1A1A1A] hover:border-[#EDEDED] transition-colors"
            >
              查看进度
            </button>
          </div>
        </div>
      </div>

      {/* 主内容区 */}
      <div className="container mx-auto px-4 py-8">
        <div className="max-w-4xl mx-auto">
          {/* 上传区域 */}
          <div
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            className={`
              border-2 border-dashed rounded-xl transition-all p-8
              ${isDragging
                ? 'border-[#EDEDED] bg-[#1A1A1A]'
                : 'border-[#1A1A1A] hover:border-[#888888]'
              }
            `}
          >
            <label className="flex flex-col items-center justify-center cursor-pointer">
              <input
                type="file"
                accept=".pdf,application/pdf"
                multiple
                onChange={handleFileSelect}
                className="hidden"
              />

              <CloudArrowUpIcon className="w-16 h-16 mb-4 text-[#888888]" />
              <p className="text-white font-medium mb-2">
                拖拽PDF文件到这里，或点击选择
              </p>
              <p className="text-[#888888] text-sm">
                支持同时上传多个PDF文件，单个文件最大80MB，最多10个
              </p>
            </label>
          </div>

          {/* 已选择的文件列表 */}
          {files.length > 0 && (
            <div className="mt-6 bg-[#0A0A0A] border border-[#1A1A1A] rounded-xl p-6">
              <h2 className="text-lg font-medium text-white mb-4">
                已选择 {files.length} 个文件
              </h2>
              <div className="space-y-3">
                {files.map((file, index) => (
                  <div key={index} className="group file-panel">
                    {/* 文件头部 */}
                    <div className="flex items-start justify-between p-4">
                      <div className="flex items-start gap-3 flex-1 min-w-0">
                        <div className="mt-0.5 file-icon-container">
                          <DocumentTextIcon className="w-5 h-5 text-white" />
                        </div>
                        <div className="flex-1 min-w-0 pt-0.5">
                          <p className="text-white text-sm font-medium truncate">
                            {file.name}
                          </p>
                          <p className="text-[#666666] text-xs mt-0.5">
                            {(file.size / 1024 / 1024).toFixed(2)} MB
                          </p>
                        </div>
                      </div>
                      <button
                        onClick={() => handleRemoveFile(index)}
                        className="p-2 text-[#666666] hover:text-red-400 hover:bg-red-400/10 rounded-lg transition-all"
                        title="删除文件"
                      >
                        <XMarkIcon className="w-5 h-5" />
                      </button>
                    </div>

                    {/* 控制面板 */}
                    <div className="px-4 pb-4">
                      <div className="flex items-stretch gap-3">
                        {/* 翻译设置 */}
                        <div className="flex items-center justify-between control-section flex-1">
                          <div className="flex items-center gap-3">
                            <LanguageIcon className="w-5 h-5 text-[#EDEDED]" />
                            <span className="text-sm text-[#EDEDED] font-medium">翻译</span>
                          </div>

                          <div className="flex items-center gap-3">
                            {file.translate && (
                              <select
                                value={file.targetLanguage || 'zh'}
                                onChange={(e) => handleTargetLanguageChange(index, e.target.value as 'zh' | 'en')}
                                className="px-3 py-1.5 bg-[#0A0A0A] text-[#EDEDED] border border-[#2A2A2A] rounded-md focus:border-[#EDEDED] focus:outline-none text-sm transition-all animate-fadeIn"
                              >
                                <option value="zh">中文</option>
                                <option value="en">English</option>
                              </select>
                            )}

                            <button
                              onClick={() => handleTranslateToggle(index, !file.translate)}
                              className={`toggle-switch ${file.translate ? 'active' : 'inactive'}`}
                            >
                              <span className="toggle-switch-thumb" />
                            </button>
                          </div>
                        </div>

                        {/* 页码范围设置 */}
                        <div className="flex items-center gap-3 control-section flex-1">
                          <div className="flex items-center gap-2 flex-shrink-0">
                            <DocumentDuplicateIcon className="w-5 h-5 text-[#EDEDED]" />
                            <span className="text-sm text-[#EDEDED] font-medium whitespace-nowrap">页码</span>
                          </div>

                          <div className="flex items-center gap-2 flex-1 min-w-0">
                            {!file.pageRangeStart && !file.pageRangeEnd ? (
                              <div className="page-range-placeholder">
                                <span className="text-[#888888] text-sm">全部页面</span>
                                <button
                                  onClick={() => {
                                    // 设置起始页为1，触发输入框显示
                                    handlePageRangeChange(index, 'start', '1');
                                  }}
                                  className="page-range-set-btn"
                                >
                                  设置范围
                                </button>
                              </div>
                            ) : (
                              <>
                                <input
                                  type="number"
                                  min="1"
                                  placeholder="起始"
                                  value={file.pageRangeStart || ''}
                                  onChange={(e) => handlePageRangeChange(index, 'start', e.target.value)}
                                  className="page-range-input"
                                />
                                <span className="text-[#666666] flex-shrink-0">—</span>
                                <input
                                  type="number"
                                  min="1"
                                  placeholder="结束"
                                  value={file.pageRangeEnd || ''}
                                  onChange={(e) => handlePageRangeChange(index, 'end', e.target.value)}
                                  className="page-range-input"
                                />
                              </>
                            )}
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              {/* 上传按钮 */}
              <button
                onClick={handleUpload}
                disabled={isUploading}
                className={`
                  mt-6 w-full px-6 py-3 rounded-lg font-medium transition-all
                  ${isUploading
                    ? 'bg-[#1A1A1A] text-[#888888] cursor-not-allowed'
                    : 'bg-[#EDEDED] text-[#0A0A0A] border-2 border-[#0A0A0A] hover:opacity-90'
                  }
                `}
              >
                {isUploading ? '上传中...' : '开始上传并解析'}
              </button>
            </div>
          )}

          {/* 使用说明 */}
          <div className="mt-6 p-4 bg-[#1A1A1A] rounded-lg">
            <h3 className="text-[#EDEDED] text-sm font-medium mb-2">使用说明</h3>
            <ul className="text-[#888888] text-sm space-y-1">
              <li>• 仅支持 PDF 格式文件</li>
              <li>• 单个文件大小限制 80MB</li>
              <li>• 最多同时上传 10 个文件</li>
              <li>• 上传后将自动开始解析</li>
              <li>• 可在进度页面查看解析状态</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
