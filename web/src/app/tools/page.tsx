'use client';

import { useEffect } from 'react';
import Link from 'next/link';
import { isAuthenticated } from '@/lib/auth-fetch';
import {
  DocumentTextIcon,
  ChatBubbleBottomCenterTextIcon,
  CpuChipIcon,
  PresentationChartBarIcon,
  UserGroupIcon,
  ClipboardDocumentCheckIcon,
  RocketLaunchIcon,
  ShoppingBagIcon,
  NewspaperIcon
} from '@heroicons/react/24/outline';

interface Tool {
  id: string;
  name: string;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
  href: string;
  category: 'document' | 'ai' | 'development' | 'analysis';
  status: 'active' | 'coming_soon' | 'beta' | 'refact';
}

const tools: Tool[] = [
  {
    id: 'pdf2md',
    name: 'PDF转Markdown',
    description: '将PDF文档智能解析转换为格式化的Markdown文本',
    icon: DocumentTextIcon,
    href: '/tools/pdf2md',
    category: 'document',
    status: 'active'
  },
  {
    id: 'chat',
    name: '个性化AI Copilot',
    description: '基于Agentic Engine的智能AI',
    icon: ChatBubbleBottomCenterTextIcon,
    href: '/chat',
    category: 'ai',
    status: 'active'
  },
  {
    id: 'presentation',
    name: 'Presentation',
    description: 'Powered by Agentic Engine，智能演示文稿生成与编辑',
    icon: PresentationChartBarIcon,
    href: '/tools/presentation',
    category: 'document',
    status: 'refact'
  },
  {
    id: 'n8n-workflow',
    name: 'n8n WorkFlow',
    description: 'Powered by Agentic Engine，自动化工作流设计与执行',
    icon: CpuChipIcon,
    href: '/tools/n8n-workflow',
    category: 'development',
    status: 'beta'
  },
  {
    id: 'team-projects',
    name: 'Team Projects',
    description: 'Powered by Agentic Engine，团队协作项目管理平台',
    icon: UserGroupIcon,
    href: '/tools/team-projects',
    category: 'development',
    status: 'coming_soon'
  },
  {
    id: 'report',
    name: 'Report',
    description: 'Powered by Agentic Engine，智能报告生成与分析',
    icon: ClipboardDocumentCheckIcon,
    href: '/tools/report',
    category: 'analysis',
    status: 'coming_soon'
  },
  {
    id: 'automatic-task',
    name: 'Automatic Task',
    description: 'Powered by Agentic Engine，自动化任务调度与执行',
    icon: RocketLaunchIcon,
    href: '/tools/automatic-task',
    category: 'ai',
    status: 'beta'
  },
  {
    id: 'ai-shopkeeper',
    name: 'AI店长模拟经营',
    description: 'Powered by Agentic Engine，门店经营决策模拟与培训平台',
    icon: ShoppingBagIcon,
    href: '/exp/aikeeper',
    category: 'ai',
    status: 'coming_soon'
  },
  {
    id: 'moments',
    name: '茶茶圈',
    description: '大家都在说什么 - 飞书公司圈帖子抓取与展示',
    icon: NewspaperIcon,
    href: '/tools/moments',
    category: 'analysis',
    status: 'active'
  }
];

const categoryConfig = {
  document: {
    name: '文档处理',
    color: 'from-blue-500/20 to-blue-600/10',
    borderColor: 'border-blue-500/30'
  },
  ai: {
    name: 'AI工具',
    color: 'from-purple-500/20 to-purple-600/10',
    borderColor: 'border-purple-500/30'
  },
  development: {
    name: '开发工具',
    color: 'from-green-500/20 to-green-600/10',
    borderColor: 'border-green-500/30'
  },
  analysis: {
    name: '分析工具',
    color: 'from-orange-500/20 to-orange-600/10',
    borderColor: 'border-orange-500/30'
  }
};

const statusConfig = {
  active: {
    label: '可用',
    className: 'bg-green-500/10 text-green-400 border-green-500/30'
  },
  beta: {
    label: 'Beta',
    className: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/30'
  },
  coming_soon: {
    label: '即将推出',
    className: 'bg-gray-500/10 text-gray-400 border-gray-500/30'
  },
  refact: {
    label: '重构中',
    className: 'bg-purple-500/10 text-purple-400 border-purple-500/30'
  }
};

export default function ToolsPage() {
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

  return (
    <div className="min-h-screen bg-black">
      {/* Hero Section */}
      <div className="relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-b from-[#1A1A1A] to-transparent opacity-50" />
        <div className="container mx-auto px-4 py-20 relative z-10">
          <div className="text-center max-w-4xl mx-auto">
            <h1 className="text-7xl font-bold bg-gradient-to-b from-white to-[#ADADAD] bg-clip-text text-transparent mb-6">
              工具中心
            </h1>
            <p className="text-[#888888] text-lg mb-8">
              探索我们为您准备的AI驱动工具集，提升工作效率
            </p>
            
            {/* 快速统计 */}
            <div className="flex justify-center gap-8 mt-12">
              <div className="text-center">
                <div className="text-3xl font-bold text-white">{tools.filter(t => t.status === 'active').length}</div>
                <div className="text-[#888888] text-sm">已上线</div>
              </div>
              <div className="text-center">
                <div className="text-3xl font-bold text-white">{tools.filter(t => t.status === 'beta').length}</div>
                <div className="text-[#888888] text-sm">测试中</div>
              </div>
              <div className="text-center">
                <div className="text-3xl font-bold text-white">{tools.filter(t => t.status === 'refact').length}</div>
                <div className="text-[#888888] text-sm">重构中</div>
              </div>
              <div className="text-center">
                <div className="text-3xl font-bold text-white">{tools.filter(t => t.status === 'coming_soon').length}</div>
                <div className="text-[#888888] text-sm">开发中</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* 分类筛选 */}
      <div className="container mx-auto px-4 py-8">
        <div className="flex justify-center gap-4 flex-wrap">
          {Object.entries(categoryConfig).map(([key, config]) => (
            <button
              key={key}
              className="px-6 py-2 bg-[#0A0A0A] text-[#EDEDED] rounded-lg border border-[#1A1A1A] hover:border-[#EDEDED] transition-colors"
            >
              {config.name}
            </button>
          ))}
        </div>
      </div>

      {/* 工具网格 */}
      <div className="container mx-auto px-4 py-12">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
          {tools.map((tool) => {
            const category = categoryConfig[tool.category];
            const status = statusConfig[tool.status];
            const Icon = tool.icon;
            
            return (
              <Link
                key={tool.id}
                href={tool.href}
                className={`
                  group relative bg-[#0A0A0A] border border-[#1A1A1A] rounded-xl p-6
                  hover:border-[#EDEDED] transition-all duration-200
                  ${tool.status !== 'active' ? 'opacity-75 pointer-events-none' : ''}
                `}
              >
                {/* 渐变背景 */}
                <div className={`absolute inset-0 bg-gradient-to-br ${category.color} rounded-xl opacity-0 group-hover:opacity-100 transition-opacity`} />
                
                <div className="relative z-10">
                  {/* 图标和状态 */}
                  <div className="flex justify-between items-start mb-4">
                    <div className={`p-3 bg-[#1A1A1A] rounded-lg border ${category.borderColor} group-hover:bg-[#0A0A0A] transition-colors`}>
                      <Icon className="w-6 h-6 text-white" />
                    </div>
                    <span className={`px-2 py-1 text-xs rounded border ${status.className}`}>
                      {status.label}
                    </span>
                  </div>
                  
                  {/* 标题和描述 */}
                  <h3 className="text-white font-semibold text-lg mb-2 group-hover:text-[#EDEDED] transition-colors">
                    {tool.name}
                  </h3>
                  <p className="text-[#888888] text-sm leading-relaxed group-hover:text-[#ADADAD] transition-colors">
                    {tool.description}
                  </p>
                  
                  {/* 分类标签 */}
                  <div className="mt-4 pt-4 border-t border-[#1A1A1A]">
                    <span className="text-[#888888] text-xs">
                      {category.name}
                    </span>
                  </div>
                </div>
              </Link>
            );
          })}
        </div>
      </div>

      {/* 底部CTA */}
      <div className="container mx-auto px-4 py-20">
        <div className="bg-[#0A0A0A] border border-[#1A1A1A] rounded-2xl p-12 text-center">
          <h2 className="text-3xl font-bold text-white mb-4">
            没有找到需要的工具？
          </h2>
          <p className="text-[#888888] mb-8">
            告诉我们您的需求，我们将为您定制开发
          </p>
          <div className="flex gap-4 justify-center">
            <button className="bg-[#EDEDED] text-[#0A0A0A] px-6 py-3 rounded-lg font-medium border-2 border-[#0A0A0A] hover:opacity-90 transition-opacity">
              提交需求
            </button>
            <button className="bg-[#0A0A0A] text-[#EDEDED] px-6 py-3 rounded-lg font-medium border border-[#EDEDED] hover:bg-[#1A1A1A] transition-colors">
              联系我们
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}