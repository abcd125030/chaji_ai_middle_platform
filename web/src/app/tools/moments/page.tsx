'use client';

import { useEffect, useState, useCallback, useRef } from 'react';
import Link from 'next/link';
import { authFetch, isAuthenticated } from '@/lib/auth-fetch';
import {
  ArrowLeftIcon,
  ArrowPathIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
} from '@heroicons/react/24/outline';

interface MomentsPost {
  id: number;
  post_id: string;
  author_open_id: string;
  author_user_id: string;
  content_text: string;
  content_raw: unknown[];
  category_ids: string[];
  feishu_create_time: string | null;
  created_at: string | null;
}

interface Pagination {
  page: number;
  page_size: number;
  total_pages: number;
  total_count: number;
  has_next: boolean;
  has_previous: boolean;
}

interface HourlyStat {
  hour: string;
  label: string;
  count: number;
}

interface StatsResponse {
  status: string;
  data: {
    hourly_stats: HourlyStat[];
    total_24h: number;
  };
}

interface PostsResponse {
  status: string;
  data: {
    items: MomentsPost[];
    pagination: Pagination;
  };
  message: string;
}

// 简单的折线图组件
function LineChart({ data }: { data: HourlyStat[] }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || data.length === 0) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);

    const width = rect.width;
    const height = rect.height;
    const padding = { top: 20, right: 20, bottom: 40, left: 40 };
    const chartWidth = width - padding.left - padding.right;
    const chartHeight = height - padding.top - padding.bottom;

    // 清空画布
    ctx.clearRect(0, 0, width, height);

    const maxCount = Math.max(...data.map(d => d.count), 1);
    const xStep = chartWidth / (data.length - 1 || 1);

    // 绘制网格线
    ctx.strokeStyle = '#1A1A1A';
    ctx.lineWidth = 1;
    for (let i = 0; i <= 4; i++) {
      const y = padding.top + (chartHeight / 4) * i;
      ctx.beginPath();
      ctx.moveTo(padding.left, y);
      ctx.lineTo(width - padding.right, y);
      ctx.stroke();
    }

    // 绘制Y轴标签
    ctx.fillStyle = '#666666';
    ctx.font = '10px sans-serif';
    ctx.textAlign = 'right';
    for (let i = 0; i <= 4; i++) {
      const value = Math.round(maxCount * (4 - i) / 4);
      const y = padding.top + (chartHeight / 4) * i;
      ctx.fillText(value.toString(), padding.left - 8, y + 3);
    }

    // 绘制X轴标签（每4小时显示一个）
    ctx.textAlign = 'center';
    data.forEach((item, index) => {
      if (index % 4 === 0 || index === data.length - 1) {
        const x = padding.left + index * xStep;
        ctx.fillText(item.label, x, height - padding.bottom + 20);
      }
    });

    // 绘制折线
    ctx.strokeStyle = '#3B82F6';
    ctx.lineWidth = 2;
    ctx.beginPath();
    data.forEach((item, index) => {
      const x = padding.left + index * xStep;
      const y = padding.top + chartHeight - (item.count / maxCount) * chartHeight;
      if (index === 0) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }
    });
    ctx.stroke();

    // 绘制数据点
    ctx.fillStyle = '#3B82F6';
    data.forEach((item, index) => {
      const x = padding.left + index * xStep;
      const y = padding.top + chartHeight - (item.count / maxCount) * chartHeight;
      ctx.beginPath();
      ctx.arc(x, y, 3, 0, Math.PI * 2);
      ctx.fill();
    });

    // 绘制渐变填充
    const gradient = ctx.createLinearGradient(0, padding.top, 0, height - padding.bottom);
    gradient.addColorStop(0, 'rgba(59, 130, 246, 0.3)');
    gradient.addColorStop(1, 'rgba(59, 130, 246, 0)');
    ctx.fillStyle = gradient;
    ctx.beginPath();
    data.forEach((item, index) => {
      const x = padding.left + index * xStep;
      const y = padding.top + chartHeight - (item.count / maxCount) * chartHeight;
      if (index === 0) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }
    });
    ctx.lineTo(padding.left + (data.length - 1) * xStep, height - padding.bottom);
    ctx.lineTo(padding.left, height - padding.bottom);
    ctx.closePath();
    ctx.fill();
  }, [data]);

  return (
    <canvas
      ref={canvasRef}
      className="w-full h-full"
      style={{ width: '100%', height: '200px' }}
    />
  );
}

export default function MomentsPage() {
  const [posts, setPosts] = useState<MomentsPost[]>([]);
  const [pagination, setPagination] = useState<Pagination | null>(null);
  const [hourlyStats, setHourlyStats] = useState<HourlyStat[]>([]);
  const [total24h, setTotal24h] = useState(0);
  const [loading, setLoading] = useState(true);
  const [statsLoading, setStatsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState(1);

  const fetchStats = useCallback(async () => {
    setStatsLoading(true);
    try {
      const response = await authFetch('/api/webapps/moments/posts/stats/hourly/');
      if (response.ok) {
        const data: StatsResponse = await response.json();
        if (data.status === 'success') {
          setHourlyStats(data.data.hourly_stats);
          setTotal24h(data.data.total_24h);
        }
      }
    } catch (err) {
      console.error('获取统计数据失败:', err);
    } finally {
      setStatsLoading(false);
    }
  }, []);

  const fetchPosts = useCallback(async (page: number) => {
    setLoading(true);
    setError(null);
    try {
      const response = await authFetch(`/api/webapps/moments/posts/?page=${page}&page_size=20`);
      if (!response.ok) {
        throw new Error(`请求失败: ${response.status}`);
      }
      const data: PostsResponse = await response.json();
      if (data.status === 'success') {
        setPosts(data.data.items);
        setPagination(data.data.pagination);
      } else {
        throw new Error(data.message || '获取数据失败');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '未知错误');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!isAuthenticated()) {
      const currentPath = window.location.pathname + window.location.search;
      const callbackUrl = encodeURIComponent(currentPath);
      const basePath = process.env.NEXT_PUBLIC_BASE_PATH || '';
      window.location.href = `${basePath}/auth/login?callbackUrl=${callbackUrl}`;
      return;
    }
    fetchStats();
    fetchPosts(currentPage);
  }, [currentPage, fetchPosts, fetchStats]);

  const handlePageChange = (newPage: number) => {
    setCurrentPage(newPage);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const handleRefresh = () => {
    fetchStats();
    fetchPosts(currentPage);
  };

  const formatDate = (dateString: string | null) => {
    if (!dateString) return '未知时间';
    const date = new Date(dateString);
    return date.toLocaleString('zh-CN', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const truncateText = (text: string, maxLength: number = 100) => {
    if (!text) return '(无内容)';
    if (text.length <= maxLength) return text;
    return text.slice(0, maxLength) + '...';
  };

  return (
    <div className="min-h-screen bg-black">
      {/* Header */}
      <div className="border-b border-[#1A1A1A]">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Link
                href="/tools"
                className="p-2 hover:bg-[#1A1A1A] rounded-lg transition-colors"
              >
                <ArrowLeftIcon className="w-5 h-5 text-[#888888]" />
              </Link>
              <div>
                <h1 className="text-xl font-bold text-white">茶茶圈 - 大家都在说什么</h1>
                <p className="text-[#888888] text-sm">
                  飞书公司圈帖子抓取与展示
                </p>
              </div>
            </div>
            <button
              onClick={handleRefresh}
              disabled={loading || statsLoading}
              className="flex items-center gap-2 px-3 py-1.5 bg-[#1A1A1A] text-white text-sm rounded-lg hover:bg-[#2A2A2A] transition-colors disabled:opacity-50"
            >
              <ArrowPathIcon className={`w-4 h-4 ${loading || statsLoading ? 'animate-spin' : ''}`} />
              刷新
            </button>
          </div>
        </div>
      </div>

      {/* Stats Chart */}
      <div className="container mx-auto px-4 py-6">
        <div className="bg-[#0A0A0A] border border-[#1A1A1A] rounded-xl p-4">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-white font-medium">24小时发帖趋势</h2>
            <span className="text-[#888888] text-sm">
              24h 总计: <span className="text-white font-medium">{total24h}</span> 条
            </span>
          </div>
          {statsLoading ? (
            <div className="h-[200px] flex items-center justify-center">
              <ArrowPathIcon className="w-6 h-6 text-[#888888] animate-spin" />
            </div>
          ) : (
            <LineChart data={hourlyStats} />
          )}
        </div>
      </div>

      {/* Posts List */}
      <div className="container mx-auto px-4 pb-8">
        {loading && posts.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12">
            <ArrowPathIcon className="w-6 h-6 text-[#888888] animate-spin mb-2" />
            <p className="text-[#888888] text-sm">加载中...</p>
          </div>
        ) : error ? (
          <div className="flex flex-col items-center justify-center py-12">
            <p className="text-red-400 text-sm mb-3">{error}</p>
            <button
              onClick={() => fetchPosts(currentPage)}
              className="px-3 py-1.5 bg-[#1A1A1A] text-white text-sm rounded-lg hover:bg-[#2A2A2A] transition-colors"
            >
              重试
            </button>
          </div>
        ) : posts.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12">
            <p className="text-[#888888] text-sm">暂无内容</p>
          </div>
        ) : (
          <>
            {/* Table Header */}
            <div className="bg-[#0A0A0A] border border-[#1A1A1A] rounded-t-xl">
              <div className="flex px-4 py-3 text-[#888888] text-sm font-medium border-b border-[#1A1A1A]">
                <div className="w-28 shrink-0">发布时间</div>
                <div className="w-24 shrink-0">发布者</div>
                <div className="w-20 shrink-0">分类</div>
                <div className="flex-1 min-w-0">内容摘要</div>
                <div className="w-16 shrink-0 text-center">查看原帖</div>
              </div>

              {/* Table Body */}
              {posts.map((post) => (
                <div
                  key={post.post_id}
                  className="flex px-4 py-3 text-sm border-b border-[#1A1A1A] last:border-b-0 hover:bg-[#111111] transition-colors"
                >
                  <div className="w-28 shrink-0 text-[#888888]">
                    {formatDate(post.feishu_create_time)}
                  </div>
                  <div className="w-24 shrink-0 text-[#ADADAD] truncate">
                    {post.author_user_id || post.author_open_id?.slice(-8) || '匿名'}
                  </div>
                  <div className="w-20 shrink-0 text-[#888888] truncate">
                    暂未分类
                  </div>
                  <div className="flex-1 min-w-0 text-[#EDEDED] truncate">
                    {truncateText(post.content_text)}
                  </div>
                  <div className="w-16 shrink-0 text-center">
                    <a
                      href={`https://applink.feishu.cn/client/moments/detail?postId=${post.post_id}&source=copy&showDepartment=true&showInteractiveInfo=true&showBottomPadding=false`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-400 hover:text-blue-300 transition-colors"
                    >
                      查看
                    </a>
                  </div>
                </div>
              ))}
            </div>

            {/* Pagination */}
            {pagination && (
              <div className="bg-[#0A0A0A] border border-t-0 border-[#1A1A1A] rounded-b-xl px-4 py-3">
                <div className="flex items-center justify-center gap-4">
                  <button
                    onClick={() => handlePageChange(currentPage - 1)}
                    disabled={!pagination.has_previous || loading}
                    className="flex items-center gap-1 px-3 py-1.5 text-sm text-[#888888] hover:text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <ChevronLeftIcon className="w-4 h-4" />
                    上一页
                  </button>
                  <span className="text-[#888888] text-sm">
                    第 <span className="text-white">{pagination.page}</span> / {pagination.total_pages} 页
                    <span className="ml-2 text-[#666666]">
                      (共 {pagination.total_count} 条)
                    </span>
                  </span>
                  <button
                    onClick={() => handlePageChange(currentPage + 1)}
                    disabled={!pagination.has_next || loading}
                    className="flex items-center gap-1 px-3 py-1.5 text-sm text-[#888888] hover:text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    下一页
                    <ChevronRightIcon className="w-4 h-4" />
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
