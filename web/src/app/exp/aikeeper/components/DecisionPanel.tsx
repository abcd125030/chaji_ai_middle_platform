'use client';

import { useState } from 'react';
import {
  CloudIcon,
  ExclamationTriangleIcon,
  ChartBarIcon,
} from '@heroicons/react/24/outline';

interface DecisionOption {
  id: string;
  label: string;
  description: string;
  risk?: 'low' | 'medium' | 'high';
}

interface DecisionScenario {
  id: string;
  dayNumber: number;
  hour: number;
  title: string;
  description: string;
  contextTags: string[];
  metrics: {
    label: string;
    value: string;
    trend?: 'up' | 'down' | 'neutral';
  }[];
  options: DecisionOption[];
}

interface DecisionPanelProps {
  scenario: DecisionScenario;
  onDecision: (optionId: string) => void;
}

export function DecisionPanel({ scenario, onDecision }: DecisionPanelProps) {
  const [selectedOption, setSelectedOption] = useState<string | null>(null);
  const [showResult, setShowResult] = useState(false);

  const handleSubmit = () => {
    if (selectedOption) {
      setShowResult(true);
      onDecision(selectedOption);
    }
  };

  const getRiskColor = (risk?: 'low' | 'medium' | 'high') => {
    if (!risk) return 'text-slate-400';
    return {
      low: 'text-green-400',
      medium: 'text-yellow-400',
      high: 'text-red-400',
    }[risk];
  };

  return (
    <div className="flex flex-col h-full">
      {/* 场景描述区 */}
      <div className="p-4 border-b border-slate-700 bg-slate-900/50">
        <div className="flex items-center gap-2 mb-2">
          <span className="text-xs text-slate-500">
            第{scenario.dayNumber}天 · {scenario.hour}:00
          </span>
        </div>
        <h3 className="text-sm font-semibold text-slate-100 mb-2">{scenario.title}</h3>
        <p className="text-xs text-slate-400 leading-relaxed mb-3">{scenario.description}</p>

        {/* 环境标签 */}
        <div className="flex flex-wrap gap-1.5 mb-3">
          {scenario.contextTags.map((tag) => (
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

        {/* 关键指标 */}
        <div className="grid grid-cols-2 gap-2">
          {scenario.metrics.map((metric) => (
            <div key={metric.label} className="bg-slate-800/30 rounded px-2 py-1.5">
              <div className="text-xs text-slate-500">{metric.label}</div>
              <div className="text-sm font-medium text-slate-200">{metric.value}</div>
            </div>
          ))}
        </div>
      </div>

      {/* 决策选项区 */}
      <div className="flex-1 overflow-y-auto p-4">
        <div className="space-y-3">
          {scenario.options.map((option) => (
            <button
              key={option.id}
              onClick={() => setSelectedOption(option.id)}
              disabled={showResult}
              className={`w-full text-left p-3 rounded-lg border transition-all ${
                selectedOption === option.id
                  ? 'border-cyan-500 bg-cyan-500/10'
                  : 'border-slate-700 bg-slate-800/30 hover:border-slate-600 hover:bg-slate-800/50'
              } ${showResult ? 'opacity-50 cursor-not-allowed' : ''}`}
            >
              <div className="flex items-start justify-between mb-1">
                <span className="text-sm font-medium text-slate-200">{option.label}</span>
                {option.risk && (
                  <span className={`text-xs ${getRiskColor(option.risk)}`}>
                    {option.risk === 'low' && '低风险'}
                    {option.risk === 'medium' && '中风险'}
                    {option.risk === 'high' && '高风险'}
                  </span>
                )}
              </div>
              <p className="text-xs text-slate-400 leading-relaxed">{option.description}</p>
            </button>
          ))}
        </div>
      </div>

      {/* 提交按钮 */}
      <div className="p-4 border-t border-slate-700 bg-slate-900/50">
        {!showResult ? (
          <button
            onClick={handleSubmit}
            disabled={!selectedOption}
            className={`w-full py-2.5 rounded-lg font-medium text-sm transition-all ${
              selectedOption
                ? 'bg-cyan-500 text-white hover:bg-cyan-600'
                : 'bg-slate-700 text-slate-500 cursor-not-allowed'
            }`}
          >
            提交决策
          </button>
        ) : (
          <div className="bg-slate-800/50 rounded-lg p-3">
            <div className="flex items-center gap-2 mb-2">
              <ChartBarIcon className="w-4 h-4 text-cyan-400" />
              <span className="text-sm font-semibold text-cyan-400">决策结果</span>
            </div>
            <p className="text-xs text-slate-400 leading-relaxed">
              正在模拟您的决策结果，系统将根据历史数据和经营模型计算影响...
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

// Mock数据生成器
export const MOCK_SCENARIOS: DecisionScenario[] = [
  {
    id: 'scenario-1',
    dayNumber: 45,
    hour: 14,
    title: '午高峰后库存预警',
    description: '午高峰刚结束，蜜桃汁库存降至安全线以下(23%)，下午茶时段(14:00-17:00)即将到来。需要决策是否紧急补货。',
    contextTags: ['库存低', '午高峰后', '下午茶时段'],
    metrics: [
      { label: '蜜桃汁库存', value: '23%', trend: 'down' },
      { label: '当前订单', value: '8分钟', trend: 'neutral' },
      { label: '在岗人数', value: '3/5', trend: 'neutral' },
      { label: '预测需求', value: '高', trend: 'up' },
    ],
    options: [
      {
        id: 'opt-1',
        label: '紧急补货5瓶(加急配送)',
        description: '联系供应商紧急配送，预计16:00送达，成本增加30%',
        risk: 'low',
      },
      {
        id: 'opt-2',
        label: '正常补货10瓶(明日送达)',
        description: '按正常流程订货，明天上午送达，成本不变但今日可能缺货',
        risk: 'medium',
      },
      {
        id: 'opt-3',
        label: '暂不补货，推荐其他产品',
        description: '培训店员推荐替代产品(花田乌龙)，节省成本但可能影响满意度',
        risk: 'high',
      },
      {
        id: 'opt-4',
        label: '补货2瓶+推荐替代',
        description: '少量补货应对急需，同时推荐替代产品，平衡成本和体验',
        risk: 'low',
      },
    ],
  },
  {
    id: 'scenario-2',
    dayNumber: 45,
    hour: 13,
    title: '竞品促销应对',
    description: '500米外的茶百道正在进行"第二杯半价"活动，午高峰客流量比预期少15%。需要决策如何应对竞争。',
    contextTags: ['竞品促销', '客流下降', '午高峰'],
    metrics: [
      { label: '客流量', value: '-15%', trend: 'down' },
      { label: '营收', value: '¥3,200', trend: 'down' },
      { label: '库存状态', value: '82%', trend: 'neutral' },
      { label: '人员状态', value: '正常', trend: 'neutral' },
    ],
    options: [
      {
        id: 'opt-1',
        label: '美团增加新客券投放',
        description: '在美团平台投放"新客立减5元"券，精准吸引价格敏感用户，预算500元',
        risk: 'low',
      },
      {
        id: 'opt-2',
        label: '门店海报宣传品质优势',
        description: '强调原叶鲜奶茶的品质优势，不跟进价格战，保持品牌定位',
        risk: 'medium',
      },
      {
        id: 'opt-3',
        label: '会员专属优惠',
        description: '给老会员推送专属折扣，维护忠诚客户，不影响新客定价',
        risk: 'low',
      },
      {
        id: 'opt-4',
        label: '观望不动',
        description: '继续正常经营，相信品牌力和产品力，避免价格战消耗',
        risk: 'high',
      },
    ],
  },
];
