import { CheckCircleIcon, XCircleIcon, ClockIcon, CloudIcon, ExclamationTriangleIcon } from '@heroicons/react/24/outline';

export interface Suggestion {
  id: string;
  observerId: string;
  observerName: string;
  observerAvatar: string;
  content: string;
  dayNumber: number;
  timestamp: string;
  hour?: number; // 建议提出的小时
  status: 'pending' | 'accepted' | 'rejected';
  contextTags?: string[]; // 环境上下文标签
  aiResponse?: {
    decision: 'accept' | 'reject';
    reasoning: string;
    executionPlan?: string;
    executed?: boolean;
  };
  acceptanceRate?: number;
}

export interface Observer {
  id: string;
  name: string;
  avatar: string;
  role: string;
  acceptanceRate: number;
  totalSuggestions: number;
}

interface SuggestionCardProps {
  suggestion: Suggestion;
}

export function SuggestionCard({ suggestion }: SuggestionCardProps) {
  const statusConfig = {
    pending: {
      icon: <ClockIcon className="w-5 h-5" />,
      color: 'text-orange-400',
      bg: 'bg-orange-500/10',
      border: 'border-orange-500/30',
      label: '待处理',
    },
    accepted: {
      icon: <CheckCircleIcon className="w-5 h-5" />,
      color: 'text-green-400',
      bg: 'bg-green-500/10',
      border: 'border-green-500/30',
      label: '已采纳',
    },
    rejected: {
      icon: <XCircleIcon className="w-5 h-5" />,
      color: 'text-slate-400',
      bg: 'bg-slate-700/30',
      border: 'border-slate-600',
      label: '未采纳',
    },
  };

  const config = statusConfig[suggestion.status];

  return (
    <div className={`rounded-lg border ${config.border} ${config.bg} p-4`}>
      {/* 头部：观测者信息 + 状态 */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className="text-2xl">{suggestion.observerAvatar}</div>
          <div>
            <div className="text-sm font-medium text-slate-200">{suggestion.observerName}</div>
            <div className="text-xs text-slate-500">
              第{suggestion.dayNumber}天 {suggestion.timestamp}
              {suggestion.acceptanceRate !== undefined && (
                <span className="ml-2 text-slate-600">· 历史采纳率 {suggestion.acceptanceRate}%</span>
              )}
            </div>
          </div>
        </div>
        <div className={`flex items-center gap-1.5 ${config.color}`}>
          {config.icon}
          <span className="text-xs font-medium">{config.label}</span>
        </div>
      </div>

      {/* 环境上下文标签 */}
      {suggestion.contextTags && suggestion.contextTags.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-3">
          {suggestion.contextTags.map((tag) => (
            <span
              key={tag}
              className="inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded bg-slate-800/50 text-slate-400 border border-slate-700"
            >
              {tag === '雨天' && <CloudIcon className="w-3 h-3" />}
              {tag === '库存低' && <ExclamationTriangleIcon className="w-3 h-3" />}
              {tag}
            </span>
          ))}
        </div>
      )}

      {/* 建议内容 */}
      <div className="text-sm text-slate-300 mb-3 leading-relaxed">{suggestion.content}</div>

      {/* AI响应 */}
      {suggestion.aiResponse && (
        <div className="bg-slate-900/50 rounded-lg p-3 space-y-2">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-full bg-cyan-500/20 flex items-center justify-center">
              <span className="text-xs">🤖</span>
            </div>
            <span className="text-xs font-semibold text-cyan-400">AI店长回应</span>
          </div>
          <p className="text-xs text-slate-400 leading-relaxed">{suggestion.aiResponse.reasoning}</p>
          {suggestion.aiResponse.executionPlan && (
            <div className="mt-2 pt-2 border-t border-slate-700">
              <div className="text-xs text-slate-500 mb-1">执行计划：</div>
              <p className="text-xs text-slate-300">{suggestion.aiResponse.executionPlan}</p>
              {suggestion.aiResponse.executed && (
                <div className="mt-1 text-xs text-green-400 flex items-center gap-1">
                  <CheckCircleIcon className="w-3 h-3" />
                  已执行
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
