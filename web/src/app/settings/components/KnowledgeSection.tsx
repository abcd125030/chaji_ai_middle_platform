'use client';

import React, { useState, useMemo } from 'react';
import { MagnifyingGlassIcon, Cog6ToothIcon } from '@heroicons/react/24/outline';
import { CalendarIcon, TagIcon } from '@heroicons/react/24/solid';

interface KnowledgeItem {
  id: string;
  title: string;
  content: string;
  created_at: string;
  updated_at: string;
  tags: string[];
  type: 'document' | 'webpage' | 'note' | 'article';
}

const mockKnowledgeItems: KnowledgeItem[] = [
  {
    id: '1',
    title: 'AI Agent 架构设计文档',
    content: '本文档详细介绍了基于 LangGraph 的 AI Agent 架构设计方案，包括节点定义、边的连接、状态管理和工作流编排。通过 Graph-Node-Edge 模式实现了灵活的任务调度和执行机制，支持条件路由、并行处理和错误恢复...',
    created_at: '2025-07-15T10:30:00Z',
    updated_at: '2025-07-20T14:20:00Z',
    tags: ['架构', 'AI Agent', 'LangGraph'],
    type: 'document'
  },
  {
    id: '2',
    title: '知识库向量检索优化方案',
    content: '针对大规模知识库的向量检索性能问题，提出了基于 Qdrant 的优化方案。通过合理的分片策略、索引优化和缓存机制，将检索速度提升了 3 倍。同时引入了混合检索策略，结合关键词匹配和语义相似度...',
    created_at: '2025-07-18T09:15:00Z',
    updated_at: '2025-07-20T16:45:00Z',
    tags: ['向量数据库', '检索优化', 'Qdrant'],
    type: 'article'
  },
  {
    id: '3',
    title: 'Prompt 工程最佳实践',
    content: '总结了在实际项目中积累的 Prompt 工程经验，包括任务分解、角色设定、上下文管理和输出格式控制等技巧。通过具体案例展示了如何针对不同场景设计有效的提示词，以及如何进行迭代优化...',
    created_at: '2025-07-12T11:20:00Z',
    updated_at: '2025-07-22T10:30:00Z',
    tags: ['Prompt', 'LLM', '最佳实践'],
    type: 'note'
  },
  {
    id: '4',
    title: 'RAG 系统实施指南',
    content: 'RAG (Retrieval-Augmented Generation) 系统的完整实施指南，涵盖文档预处理、向量化、检索策略和生成优化等各个环节。重点介绍了如何处理长文档、表格数据和多模态内容，以及如何评估和改进系统性能...',
    created_at: '2025-07-10T14:00:00Z',
    updated_at: '2025-07-21T09:15:00Z',
    tags: ['RAG', '检索增强', '实施指南'],
    type: 'document'
  },
  {
    id: '5',
    title: '多轮对话管理机制',
    content: '深入分析了多轮对话系统的状态管理和上下文维护机制。介绍了基于 Redis 的会话缓存方案、对话历史压缩算法和动态上下文窗口调整策略。通过实际案例展示了如何处理复杂的对话场景...',
    created_at: '2025-07-08T15:30:00Z',
    updated_at: '2025-07-16T11:45:00Z',
    tags: ['对话系统', '状态管理', 'Redis'],
    type: 'article'
  },
  {
    id: '6',
    title: 'Fine-tuning 实验报告',
    content: '基于 Qwen 模型的 Fine-tuning 实验报告，对比了不同的训练策略和超参数设置对模型性能的影响。实验结果表明，采用 LoRA 技术可以在保持模型性能的同时显著减少训练成本。报告还包含了详细的数据集准备流程...',
    created_at: '2025-07-05T13:25:00Z',
    updated_at: '2025-07-15T17:20:00Z',
    tags: ['Fine-tuning', 'Qwen', 'LoRA'],
    type: 'document'
  },
  {
    id: '7',
    title: 'API 网关设计规范',
    content: '定义了 AI 中台 API 网关的设计规范，包括认证授权、限流熔断、日志监控和错误处理等方面。规范了 RESTful 接口设计原则，统一了响应格式和错误码体系。还提供了性能优化和安全加固的建议...',
    created_at: '2025-07-03T10:00:00Z',
    updated_at: '2025-07-18T14:30:00Z',
    tags: ['API', '网关', '规范'],
    type: 'document'
  },
  {
    id: '8',
    title: '工具函数集成方案',
    content: '介绍了如何将外部工具函数集成到 AI Agent 系统中。涵盖了工具注册机制、参数验证、错误处理和结果解析等关键环节。通过插件化架构实现了工具的动态加载和热更新，支持 Python、JavaScript 等多种语言...',
    created_at: '2025-07-02T09:45:00Z',
    updated_at: '2025-07-11T15:15:00Z',
    tags: ['工具集成', '插件架构', 'Agent'],
    type: 'webpage'
  }
];

const KnowledgeSection: React.FC = () => {
  const [searchQuery, setSearchQuery] = useState('');

  const filteredItems = useMemo(() => {
    return mockKnowledgeItems.filter(item => {
      const matchesSearch = searchQuery === '' || 
        item.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
        item.content.toLowerCase().includes(searchQuery.toLowerCase()) ||
        item.tags.some(tag => tag.toLowerCase().includes(searchQuery.toLowerCase()));
      
      return matchesSearch;
    });
  }, [searchQuery]);


  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('zh-CN', { 
      year: 'numeric', 
      month: '2-digit', 
      day: '2-digit' 
    });
  };

  return (
    <div className="w-full">
      <h2 className="text-2xl font-semibold text-[var(--foreground)] mb-6">
        Knowledge Base
      </h2>

      {/* Search Section with Management Icon */}
      <div className="mb-6 flex items-center gap-3">
        <div className="relative flex-1">
          <MagnifyingGlassIcon className="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-[var(--muted-foreground)]" />
          <input
            type="text"
            placeholder="搜索知识库内容、标题或标签..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-3 bg-[var(--accent)] border border-[var(--border)] rounded-lg text-[var(--foreground)] placeholder:text-[#888888] focus:outline-none focus:border-[var(--foreground)] transition-colors"
          />
        </div>
        
        {/* Management Icon */}
        <button
          className="p-3 bg-[var(--accent)] border border-[var(--border)] rounded-lg hover:border-[var(--muted-foreground)] transition-colors group"
          title="管理知识库"
        >
          <Cog6ToothIcon className="h-5 w-5 text-[var(--muted-foreground)] group-hover:text-[var(--foreground)] transition-colors" />
        </button>
      </div>

      {/* Knowledge Items Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-3 2xl:grid-cols-3 gap-4">
        {filteredItems.map((item) => (
          <div
            key={item.id}
            className="bg-[var(--accent)] rounded-lg p-4 hover:shadow-lg transition-all duration-200 border border-[var(--border)] hover:border-[var(--muted-foreground)] cursor-pointer group flex flex-col"
          >
            {/* Title - fixed 2 lines height */}
            <h3 className="text-sm font-semibold text-[var(--foreground)] h-10 line-clamp-2 group-hover:text-[var(--foreground)]/80 transition-colors mb-3">
              {item.title}
            </h3>

            {/* Content Preview */}
            <p className="text-xs text-[var(--muted-foreground)] line-clamp-3 mb-3">
              {item.content}
            </p>

            {/* Tags */}
            <div className="flex flex-wrap gap-1 mb-3 flex-1">
              {item.tags.slice(0, 3).map((tag, index) => (
                <span
                  key={index}
                  className="inline-flex items-center gap-1 px-2 py-1 text-xs bg-[var(--accent)] text-[var(--muted-foreground)] border border-[var(--border)] rounded-md h-fit"
                >
                  <TagIcon className="h-3 w-3" />
                  {tag}
                </span>
              ))}
            </div>

            {/* Meta Information - aligned to bottom */}
            <div className="pt-3 border-t border-[var(--border)] mt-auto">
              <div className="flex items-center gap-2 text-xs text-[var(--muted-foreground)]">
                <CalendarIcon className="h-3 w-3" />
                <span>更新: {formatDate(item.updated_at)}</span>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Empty State */}
      {filteredItems.length === 0 && (
        <div className="text-center py-12">
          <div className="text-6xl mb-4">🔍</div>
          <p className="text-[var(--muted-foreground)]">
            没有找到匹配的知识条目
          </p>
          <p className="text-sm text-[var(--muted-foreground)] mt-2">
            尝试调整搜索关键词或筛选条件
          </p>
        </div>
      )}

      {/* Statistics */}
      <div className="mt-8 pt-6 border-t border-[var(--border)]">
        <div className="flex items-center justify-between text-sm text-[var(--muted-foreground)]">
          <span>共 {filteredItems.length} 个知识条目</span>
          <span>最近更新: {formatDate(mockKnowledgeItems[0].updated_at)}</span>
        </div>
      </div>
    </div>
  );
};

export default KnowledgeSection;