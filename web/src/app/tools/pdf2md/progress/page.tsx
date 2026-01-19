'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { authFetch, isAuthenticated } from '@/lib/auth-fetch';
import toast from 'react-hot-toast';
import {
  DocumentTextIcon,
  ArrowPathIcon,
  CheckCircleIcon,
  ExclamationCircleIcon,
  ClockIcon,
  EyeIcon
} from '@heroicons/react/24/outline';

interface TaskProgress {
  task_id: string;
  original_filename: string;
  status: 'pending' | 'processing' | 'completed' | 'error' | 'not_found';
  total_pages: number;
  processed_pages: number;
  created_at: string;
  updated_at: string;
  message?: string;
}

/**
 * PDF解析进度页面
 * 显示所有PDF解析任务的进度状态
 */
export default function PDF2MDProgressPage() {
  const router = useRouter();
  const [tasks, setTasks] = useState<TaskProgress[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 10;

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
   * 从localStorage获取任务ID列表
   */
  const getTaskIds = (): string[] => {
    if (typeof window === 'undefined') return [];
    const stored = localStorage.getItem('pdf2md_task_ids');
    return stored ? JSON.parse(stored) : [];
  };

  /**
   * 保存任务ID到localStorage
   */
  const saveTaskIds = (taskIds: string[]) => {
    if (typeof window === 'undefined') return;
    localStorage.setItem('pdf2md_task_ids', JSON.stringify(taskIds));
  };

  /**
   * 从服务器加载所有历史任务
   */
  const fetchAllTasks = useCallback(async () => {
    setIsLoading(true);
    try {
      const response = await authFetch('/api/webapps/toolkit/extractor/tasks/?page=1&page_size=100', {
        method: 'GET'
      });

      const data = await response.json();

      if (data.status === 'success') {
        const allTasks = data.data.tasks;
        setTasks(allTasks);

        // 将所有任务ID保存到localStorage
        const allTaskIds = allTasks.map((t: TaskProgress) => t.task_id);
        saveTaskIds(allTaskIds);

        toast.success(`已加载 ${allTasks.length} 个历史任务`);
      } else {
        throw new Error(data.message || '加载历史任务失败');
      }
    } catch (error) {
      console.error('加载历史任务失败:', error);
      toast.error(error instanceof Error ? error.message : '加载历史任务失败');
    } finally {
      setIsLoading(false);
    }
  }, []);

  /**
   * 查询任务进度
   */
  const fetchProgress = useCallback(async () => {
    const taskIds = getTaskIds();
    if (taskIds.length === 0) {
      setTasks([]);
      return;
    }

    setIsLoading(true);
    try {
      const response = await authFetch('/api/webapps/toolkit/extractor/progress/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          task_ids: taskIds
        })
      });

      const data = await response.json();

      if (data.status === 'success') {
        const tasks = data.data.tasks;
        // 按更新时间倒序排序（最新的在上面）
        const sortedTasks = tasks.sort((a: TaskProgress, b: TaskProgress) => {
          return new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime();
        });
        setTasks(sortedTasks);

        // 自动清理不存在的任务ID
        const notFoundTaskIds = tasks
          .filter((t: TaskProgress) => t.status === 'not_found')
          .map((t: TaskProgress) => t.task_id);

        if (notFoundTaskIds.length > 0) {
          const validTaskIds = taskIds.filter(id => !notFoundTaskIds.includes(id));
          saveTaskIds(validTaskIds);
          console.log(`已清理 ${notFoundTaskIds.length} 个不存在的任务ID`);
        }
      } else {
        throw new Error(data.message || '获取进度失败');
      }
    } catch (error) {
      console.error('获取进度失败:', error);
      toast.error(error instanceof Error ? error.message : '获取进度失败');
    } finally {
      setIsLoading(false);
    }
  }, []);

  /**
   * 初始化和自动刷新
   */
  useEffect(() => {
    const taskIds = getTaskIds();

    // 如果localStorage为空，尝试从服务器加载历史任务
    if (taskIds.length === 0) {
      fetchAllTasks();
    } else {
      fetchProgress();
    }

    if (autoRefresh) {
      const interval = setInterval(() => {
        fetchProgress();
      }, 5000); // 每5秒刷新一次

      return () => clearInterval(interval);
    }
  }, [autoRefresh, fetchAllTasks, fetchProgress]);

  /**
   * 检查是否有处理中的任务，如果没有则自动关闭轮询
   */
  useEffect(() => {
    // 检查是否有处理中或等待中的任务
    const hasActiveTasks = tasks.some(
      task => task.status === 'processing' || task.status === 'pending'
    );

    // 如果没有活跃任务且自动刷新开启，则关闭自动刷新
    if (!hasActiveTasks && autoRefresh && tasks.length > 0) {
      setAutoRefresh(false);
      console.log('所有任务已完成或出错，已自动停止轮询');
      toast.success('所有任务已完成，已自动停止刷新', { duration: 3000 });
    }
  }, [tasks, autoRefresh]);

  /**
   * 获取状态显示信息
   */
  const getStatusInfo = (status: string) => {
    switch (status) {
      case 'pending':
        return {
          icon: <ClockIcon className="w-5 h-5 text-yellow-400" />,
          text: '等待中',
          color: 'text-yellow-400'
        };
      case 'processing':
        return {
          icon: <ArrowPathIcon className="w-5 h-5 text-blue-400 animate-spin" />,
          text: '处理中',
          color: 'text-blue-400'
        };
      case 'completed':
        return {
          icon: <CheckCircleIcon className="w-5 h-5 text-green-400" />,
          text: '已完成',
          color: 'text-green-400'
        };
      case 'error':
        return {
          icon: <ExclamationCircleIcon className="w-5 h-5 text-red-400" />,
          text: '错误',
          color: 'text-red-400'
        };
      default:
        return {
          icon: <ExclamationCircleIcon className="w-5 h-5 text-gray-400" />,
          text: '未知',
          color: 'text-gray-400'
        };
    }
  };

  /**
   * 查看任务详情
   */
  const handleViewTask = (taskId: string, status: string) => {
    if (status === 'completed') {
      router.push(`/tools/pdf2md/content/${taskId}`);
    } else {
      toast('任务尚未完成，无法查看内容', { icon: '⚠️' });
    }
  };

  /**
   * 清除已完成的任务
   */
  const handleClearCompleted = () => {
    const remainingTaskIds = tasks
      .filter(task => task.status !== 'completed')
      .map(task => task.task_id);

    saveTaskIds(remainingTaskIds);
    setTasks(tasks.filter(task => task.status !== 'completed'));
    setCurrentPage(1);
    toast.success('已清除完成的任务');
  };

  /**
   * 清除所有任务
   */
  const handleClearAll = () => {
    if (confirm('确定要清除所有任务记录吗？此操作不可恢复。')) {
      saveTaskIds([]);
      setTasks([]);
      setCurrentPage(1);
      toast.success('已清除所有任务');
    }
  };

  /**
   * 计算分页数据
   */
  const totalPages = Math.ceil(tasks.length / itemsPerPage);
  const startIndex = (currentPage - 1) * itemsPerPage;
  const endIndex = startIndex + itemsPerPage;
  const currentTasks = tasks.slice(startIndex, endIndex);

  /**
   * 切换页面
   */
  const handlePageChange = (page: number) => {
    setCurrentPage(page);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  return (
    <div className="min-h-screen bg-black">
      {/* 顶部导航栏 */}
      <div className="border-b border-[#1A1A1A] bg-[#0A0A0A]">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <DocumentTextIcon className="w-6 h-6 text-white" />
              <h1 className="text-xl font-semibold text-white">解析进度</h1>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={fetchAllTasks}
                disabled={isLoading}
                className="px-4 py-2 bg-[#0A0A0A] text-[#EDEDED] rounded-lg border border-[#1A1A1A] hover:border-[#EDEDED] transition-colors disabled:opacity-50"
                title="从服务器加载所有历史任务"
              >
                加载历史任务
              </button>
              <button
                onClick={() => setAutoRefresh(!autoRefresh)}
                className={`px-4 py-2 rounded-lg border transition-colors ${
                  autoRefresh
                    ? 'bg-[#EDEDED] text-[#0A0A0A] border-[#0A0A0A]'
                    : 'bg-[#0A0A0A] text-[#EDEDED] border-[#1A1A1A] hover:border-[#EDEDED]'
                }`}
              >
                {autoRefresh ? '停止自动刷新' : '开启自动刷新'}
              </button>
              <button
                onClick={fetchProgress}
                disabled={isLoading}
                className="px-4 py-2 bg-[#0A0A0A] text-[#EDEDED] rounded-lg border border-[#1A1A1A] hover:border-[#EDEDED] transition-colors disabled:opacity-50"
              >
                <ArrowPathIcon className={`w-5 h-5 ${isLoading ? 'animate-spin' : ''}`} />
              </button>
              <button
                onClick={() => router.push('/tools/pdf2md')}
                className="px-4 py-2 bg-[#0A0A0A] text-[#EDEDED] rounded-lg border border-[#1A1A1A] hover:border-[#EDEDED] transition-colors"
              >
                上传新文件
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* 主内容区 */}
      <div className="container mx-auto px-4 py-8">
        <div className="max-w-6xl mx-auto">
          {/* 统计信息 */}
          <div className="grid grid-cols-4 gap-4 mb-6">
            <div className="bg-[#0A0A0A] border border-[#1A1A1A] rounded-xl p-4">
              <p className="text-[#888888] text-sm mb-1">总任务数</p>
              <p className="text-white text-2xl font-semibold">{tasks.length}</p>
            </div>
            <div className="bg-[#0A0A0A] border border-[#1A1A1A] rounded-xl p-4">
              <p className="text-[#888888] text-sm mb-1">处理中</p>
              <p className="text-blue-400 text-2xl font-semibold">
                {tasks.filter(t => t.status === 'processing').length}
              </p>
            </div>
            <div className="bg-[#0A0A0A] border border-[#1A1A1A] rounded-xl p-4">
              <p className="text-[#888888] text-sm mb-1">已完成</p>
              <p className="text-green-400 text-2xl font-semibold">
                {tasks.filter(t => t.status === 'completed').length}
              </p>
            </div>
            <div className="bg-[#0A0A0A] border border-[#1A1A1A] rounded-xl p-4">
              <p className="text-[#888888] text-sm mb-1">失败</p>
              <p className="text-red-400 text-2xl font-semibold">
                {tasks.filter(t => t.status === 'error').length}
              </p>
            </div>
          </div>

          {/* 操作按钮 */}
          {tasks.length > 0 && (
            <div className="mb-4 flex gap-2">
              {tasks.some(t => t.status === 'completed') && (
                <button
                  onClick={handleClearCompleted}
                  className="px-4 py-2 bg-[#0A0A0A] text-[#888888] rounded-lg border border-[#1A1A1A] hover:border-yellow-500 hover:text-yellow-400 transition-colors"
                >
                  清除已完成任务
                </button>
              )}
              <button
                onClick={handleClearAll}
                className="px-4 py-2 bg-[#0A0A0A] text-[#888888] rounded-lg border border-[#1A1A1A] hover:border-red-500 hover:text-red-400 transition-colors"
              >
                清除全部
              </button>
            </div>
          )}

          {/* 任务列表 */}
          {tasks.length === 0 ? (
            <div className="bg-[#0A0A0A] border border-[#1A1A1A] rounded-xl p-12 text-center">
              <DocumentTextIcon className="w-16 h-16 mx-auto mb-4 text-[#888888]" />
              <p className="text-white text-lg mb-2">暂无任务</p>
              <p className="text-[#888888] text-sm mb-6">
                点击&ldquo;上传新文件&rdquo;开始解析PDF文档
              </p>
              <button
                onClick={() => router.push('/tools/pdf2md')}
                className="px-6 py-3 bg-[#EDEDED] text-[#0A0A0A] border-2 border-[#0A0A0A] rounded-lg font-medium hover:opacity-90 transition-all"
              >
                上传新文件
              </button>
            </div>
          ) : (
            <>
              <div className="space-y-4">
                {currentTasks.map((task) => {
                const statusInfo = getStatusInfo(task.status);
                const progress = task.total_pages > 0
                  ? (task.processed_pages / task.total_pages) * 100
                  : 0;

                return (
                  <div
                    key={task.task_id}
                    className="bg-[#0A0A0A] border border-[#1A1A1A] rounded-xl p-6 hover:border-[#888888] transition-colors"
                  >
                    <div className="flex items-start justify-between mb-4">
                      <div className="flex items-start gap-3 flex-1">
                        <DocumentTextIcon className="w-6 h-6 text-[#EDEDED] mt-1" />
                        <div className="flex-1">
                          <h3 className="text-white font-medium mb-1">
                            {task.original_filename}
                          </h3>
                          <div className="flex items-center gap-2 text-sm">
                            {statusInfo.icon}
                            <span className={statusInfo.color}>
                              {statusInfo.text}
                            </span>
                            {task.status === 'processing' && task.total_pages > 0 && (
                              <span className="text-[#888888]">
                                - {task.processed_pages}/{task.total_pages} 页
                              </span>
                            )}
                          </div>
                          {task.message && (
                            <p className="text-[#888888] text-sm mt-1">{task.message}</p>
                          )}
                        </div>
                      </div>

                      {task.status === 'completed' && (
                        <button
                          onClick={() => handleViewTask(task.task_id, task.status)}
                          className="flex items-center gap-2 px-4 py-2 bg-[#1A1A1A] text-[#EDEDED] rounded-lg border border-[#1A1A1A] hover:border-[#EDEDED] transition-colors"
                        >
                          <EyeIcon className="w-4 h-4" />
                          查看内容
                        </button>
                      )}
                    </div>

                    {/* 进度条 */}
                    {task.status === 'processing' && task.total_pages > 0 && (
                      <div className="w-full bg-[#1A1A1A] rounded-full h-2">
                        <div
                          className="bg-blue-400 h-2 rounded-full transition-all duration-500"
                          style={{ width: `${progress}%` }}
                        />
                      </div>
                    )}

                    {/* 时间信息 */}
                    <div className="mt-4 flex items-center gap-4 text-xs text-[#888888]">
                      <span>创建: {new Date(task.created_at).toLocaleString()}</span>
                      <span>更新: {new Date(task.updated_at).toLocaleString()}</span>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* 分页控件 */}
            {totalPages > 1 && (
              <div className="mt-8 flex items-center justify-center gap-2">
                <button
                  onClick={() => handlePageChange(currentPage - 1)}
                  disabled={currentPage === 1}
                  className="px-4 py-2 bg-[#0A0A0A] text-[#EDEDED] rounded-lg border border-[#1A1A1A] hover:border-[#EDEDED] transition-colors disabled:opacity-30 disabled:cursor-not-allowed disabled:hover:border-[#1A1A1A]"
                >
                  上一页
                </button>

                <div className="flex items-center gap-1">
                  {Array.from({ length: totalPages }, (_, i) => i + 1).map((page) => {
                    // 显示逻辑：始终显示第1页、最后一页、当前页及其前后各1页
                    const isFirstPage = page === 1;
                    const isLastPage = page === totalPages;
                    const isCurrentPage = page === currentPage;
                    const isNearCurrent = Math.abs(page - currentPage) <= 1;

                    if (isFirstPage || isLastPage || isCurrentPage || isNearCurrent) {
                      return (
                        <button
                          key={page}
                          onClick={() => handlePageChange(page)}
                          className={`px-4 py-2 rounded-lg border transition-colors ${
                            page === currentPage
                              ? 'bg-[#EDEDED] text-[#0A0A0A] border-[#0A0A0A]'
                              : 'bg-[#0A0A0A] text-[#EDEDED] border-[#1A1A1A] hover:border-[#EDEDED]'
                          }`}
                        >
                          {page}
                        </button>
                      );
                    } else if (
                      (page === currentPage - 2 && page > 1) ||
                      (page === currentPage + 2 && page < totalPages)
                    ) {
                      return (
                        <span key={page} className="px-2 text-[#888888]">
                          ...
                        </span>
                      );
                    }
                    return null;
                  })}
                </div>

                <button
                  onClick={() => handlePageChange(currentPage + 1)}
                  disabled={currentPage === totalPages}
                  className="px-4 py-2 bg-[#0A0A0A] text-[#EDEDED] rounded-lg border border-[#1A1A1A] hover:border-[#EDEDED] transition-colors disabled:opacity-30 disabled:cursor-not-allowed disabled:hover:border-[#1A1A1A]"
                >
                  下一页
                </button>

                <span className="ml-4 text-[#888888] text-sm">
                  第 {currentPage} / {totalPages} 页，共 {tasks.length} 条任务
                </span>
              </div>
            )}
          </>
          )}
        </div>
      </div>
    </div>
  );
}
