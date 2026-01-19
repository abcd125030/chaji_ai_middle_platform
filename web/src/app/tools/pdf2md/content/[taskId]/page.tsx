'use client';

import { useState, useEffect, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { authFetch, isAuthenticated } from '@/lib/auth-fetch';
import toast from 'react-hot-toast';
import { MarkdownRenderer } from '@/components/markdown-renderer';
import {
  DocumentTextIcon,
  ArrowDownTrayIcon,
  ClipboardDocumentIcon,
  CheckIcon,
  ArrowLeftIcon
} from '@heroicons/react/24/outline';

interface TaskContent {
  task_id: string;
  original_filename: string;
  markdown: string;
  images: string[];
  total_pages: number;
  feishu_doc_url: string | null;
}

/**
 * PDF内容详情页面
 * 显示解析后的markdown内容
 */
export default function PDF2MDContentPage() {
  const params = useParams();
  const router = useRouter();
  const taskId = params.taskId as string;

  const [content, setContent] = useState<TaskContent | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [copySuccess, setCopySuccess] = useState(false);

  /**
   * 检查登录状态
   */
  useEffect(() => {
    if (!isAuthenticated()) {
      const currentPath = window.location.pathname + window.location.search;
      const callbackUrl = encodeURIComponent(currentPath);
      const basePath = process.env.NEXT_PUBLIC_BASE_PATH || '';
      window.location.href = `${basePath}/auth/login?callbackUrl=${callbackUrl}`;
    }
  }, []);

  /**
   * 获取任务内容
   */
  const fetchContent = useCallback(async () => {
    setIsLoading(true);
    try {
      const response = await authFetch(
        `/api/webapps/toolkit/extractor/content/${taskId}/`
      );

      const data = await response.json();

      if (data.status === 'success') {
        setContent(data.data);
      } else {
        throw new Error(data.message || '获取内容失败');
      }
    } catch (error) {
      console.error('获取内容失败:', error);
      toast.error(error instanceof Error ? error.message : '获取内容失败');
      // 如果获取失败，返回进度页面
      setTimeout(() => router.push('/tools/pdf2md/progress'), 2000);
    } finally {
      setIsLoading(false);
    }
  }, [taskId, router]);

  useEffect(() => {
    if (taskId) {
      fetchContent();
    }
  }, [taskId, fetchContent]);

  /**
   * 复制markdown内容
   */
  const handleCopy = async () => {
    if (!content) return;

    try {
      await navigator.clipboard.writeText(content.markdown);
      setCopySuccess(true);
      toast.success('已复制到剪贴板');
      setTimeout(() => setCopySuccess(false), 2000);
    } catch {
      toast.error('复制失败');
    }
  };

  /**
   * 下载markdown文件
   */
  const handleDownload = () => {
    if (!content) return;

    const blob = new Blob([content.markdown], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${content.original_filename.replace('.pdf', '')}.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    toast.success('下载成功');
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-black flex items-center justify-center">
        <div className="text-center">
          <div className="w-16 h-16 border-4 border-[#1A1A1A] border-t-[#EDEDED] rounded-full animate-spin mx-auto mb-4" />
          <p className="text-[#888888]">加载中...</p>
        </div>
      </div>
    );
  }

  if (!content) {
    return (
      <div className="min-h-screen bg-black flex items-center justify-center">
        <div className="text-center">
          <DocumentTextIcon className="w-16 h-16 mx-auto mb-4 text-[#888888]" />
          <p className="text-white text-lg mb-2">内容不存在</p>
          <button
            onClick={() => router.push('/tools/pdf2md/progress')}
            className="px-6 py-3 bg-[#EDEDED] text-[#0A0A0A] rounded-lg font-medium hover:opacity-90"
          >
            返回进度页面
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-black">
      {/* 顶部导航栏 */}
      <div className="border-b border-[#1A1A1A] bg-[#0A0A0A]">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <button
                onClick={() => router.push('/tools/pdf2md/progress')}
                className="p-2 text-[#EDEDED] hover:text-white transition-colors"
              >
                <ArrowLeftIcon className="w-5 h-5" />
              </button>
              <DocumentTextIcon className="w-6 h-6 text-white" />
              <div>
                <h1 className="text-xl font-semibold text-white">
                  {content.original_filename}
                </h1>
                <p className="text-sm text-[#888888]">共 {content.total_pages} 页</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              {content.feishu_doc_url && (
                <button
                  onClick={() => window.open(content.feishu_doc_url!, '_blank')}
                  className="flex items-center gap-2 px-4 py-2 bg-[#0A0A0A] text-[#EDEDED] rounded-lg border border-[#1A1A1A] hover:border-[#EDEDED] transition-colors"
                >
                  <DocumentTextIcon className="w-4 h-4" />
                  查看飞书文档
                </button>
              )}
              <button
                onClick={handleCopy}
                className="flex items-center gap-2 px-4 py-2 bg-[#0A0A0A] text-[#EDEDED] rounded-lg border border-[#1A1A1A] hover:border-[#EDEDED] transition-colors"
              >
                {copySuccess ? (
                  <>
                    <CheckIcon className="w-4 h-4" />
                    已复制
                  </>
                ) : (
                  <>
                    <ClipboardDocumentIcon className="w-4 h-4" />
                    复制
                  </>
                )}
              </button>
              <button
                onClick={handleDownload}
                className="flex items-center gap-2 px-4 py-2 bg-[#0A0A0A] text-[#EDEDED] rounded-lg border border-[#1A1A1A] hover:border-[#EDEDED] transition-colors"
              >
                <ArrowDownTrayIcon className="w-4 h-4" />
                下载
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* 主内容区 */}
      <div className="container mx-auto px-4 py-8">
        <div className="max-w-4xl mx-auto">
          {/* Markdown内容预览 */}
          <div className="bg-[#0A0A0A] border border-[#1A1A1A] rounded-xl p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-medium text-white">内容预览</h2>
              <span className="text-[#888888] text-sm">
                {content.markdown.length} 字符
              </span>
            </div>

            {content.markdown ? (
              <div className="bg-[#1A1A1A] rounded-lg p-6 overflow-auto max-h-[70vh]">
                <MarkdownRenderer
                  content={content.markdown}
                  baseUrl={process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:6066'}
                />
              </div>
            ) : (
              <div className="bg-[#1A1A1A] rounded-lg p-12 text-center">
                <DocumentTextIcon className="w-12 h-12 mx-auto mb-3 text-[#888888]" />
                <p className="text-[#888888]">暂无内容</p>
              </div>
            )}
          </div>

          {/* 图片已嵌入在 Markdown 中，无需单独显示 */}

          {/* 底部操作提示 */}
          <div className="mt-6 p-4 bg-[#1A1A1A] rounded-lg">
            <h3 className="text-[#EDEDED] text-sm font-medium mb-2">操作提示</h3>
            <ul className="text-[#888888] text-sm space-y-1">
              <li>• 点击「复制」按钮复制全部 Markdown 内容</li>
              <li>• 点击「下载」按钮下载为 .md 文件</li>
              <li>• 图片已嵌入在 Markdown 中，点击图片可放大查看</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
