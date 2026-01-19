'use client';

import React, { useState } from 'react';
import { 
  CpuChipIcon, 
  DocumentDuplicateIcon, 
  TrashIcon,
  PencilIcon,
  PlayIcon,
  ArrowDownTrayIcon,
  PlusIcon
} from '@heroicons/react/24/outline';

interface Flow {
  id: string;
  name: string;
  description: string;
  category: 'automation' | 'data_processing' | 'integration' | 'notification';
  createdAt: string;
  updatedAt: string;
  nodes: number;
  active: boolean;
  jsonConfig: object;
}

const mockFlows: Flow[] = [
  {
    id: 'flow-1',
    name: '数据报表自动生成',
    description: '通过读取用户上传的文件，执行固定模式和路径的分析流程，分析拼接成上下文，最后通过LLM按照固定模板解读数据生成对应数据维度的图表。',
    category: 'automation',
    createdAt: '2025-07-15',
    updatedAt: '2025-09-20',
    nodes: 12,
    active: true,
    jsonConfig: {
      "name": "数据报表自动生成",
      "nodes": [
        {
          "id": "trigger_1",
          "type": "webhook",
          "name": "文件上传接收器",
          "position": [250, 300],
          "typeVersion": 1,
          "webhookId": "data-report-upload"
        },
        {
          "id": "file_processor_1",
          "type": "readBinaryFile",
          "name": "读取上传文件",
          "position": [450, 300],
          "parameters": {
            "fileFormat": "auto",
            "options": {
              "acceptedFormats": ["xlsx", "csv", "json"]
            }
          }
        },
        {
          "id": "data_validator_1",
          "type": "function",
          "name": "数据验证和预处理",
          "position": [650, 300],
          "parameters": {
            "functionCode": "// 验证数据结构\n// 清洗异常值\n// 标准化数据格式\nconst data = $input.all();\nreturn validateAndClean(data);"
          }
        },
        {
          "id": "pattern_analyzer_1",
          "type": "function",
          "name": "固定模式分析",
          "position": [850, 300],
          "parameters": {
            "analysisPatterns": [
              "时序分析",
              "分类统计",
              "趋势分析",
              "异常检测"
            ]
          }
        },
        {
          "id": "context_builder_1",
          "type": "aggregate",
          "name": "上下文拼接",
          "position": [1050, 300],
          "parameters": {
            "aggregateBy": "merge",
            "options": {
              "includeMetadata": true,
              "includeStatistics": true,
              "includePatterns": true
            }
          }
        },
        {
          "id": "llm_processor_1",
          "type": "openAi",
          "name": "LLM数据解读",
          "position": [1250, 300],
          "parameters": {
            "resource": "chat",
            "model": "gpt-4",
            "prompt": {
              "system": "你是一个专业的数据分析师，请根据提供的数据分析结果，按照以下模板生成报表：\n1. 数据概览\n2. 关键指标分析\n3. 趋势洞察\n4. 异常点说明\n5. 业务建议",
              "template": "基于以下数据分析结果：{{context}}，请生成专业的数据报表"
            }
          }
        },
        {
          "id": "chart_generator_1",
          "type": "function",
          "name": "图表生成器",
          "position": [1450, 300],
          "parameters": {
            "chartTypes": [
              {"type": "line", "dimension": "时间趋势"},
              {"type": "bar", "dimension": "分类对比"},
              {"type": "pie", "dimension": "占比分析"},
              {"type": "heatmap", "dimension": "相关性"}
            ],
            "library": "echarts"
          }
        },
        {
          "id": "report_formatter_1",
          "type": "htmlTemplate",
          "name": "报表格式化",
          "position": [1650, 300],
          "parameters": {
            "template": "professional-report",
            "includeCharts": true,
            "format": "html"
          }
        },
        {
          "id": "export_handler_1",
          "type": "writeBinaryFile",
          "name": "导出处理器",
          "position": [1850, 300],
          "parameters": {
            "formats": ["pdf", "excel", "html"],
            "fileName": "data_report_{{timestamp}}"
          }
        },
        {
          "id": "notification_1",
          "type": "emailSend",
          "name": "发送通知",
          "position": [2050, 300],
          "parameters": {
            "attachReport": true,
            "recipients": "{{userEmail}}"
          }
        }
      ],
      "connections": {
        "trigger_1": {
          "main": [
            [{"node": "file_processor_1", "type": "main", "index": 0}]
          ]
        },
        "file_processor_1": {
          "main": [
            [{"node": "data_validator_1", "type": "main", "index": 0}]
          ]
        },
        "data_validator_1": {
          "main": [
            [{"node": "pattern_analyzer_1", "type": "main", "index": 0}]
          ]
        },
        "pattern_analyzer_1": {
          "main": [
            [{"node": "context_builder_1", "type": "main", "index": 0}]
          ]
        },
        "context_builder_1": {
          "main": [
            [{"node": "llm_processor_1", "type": "main", "index": 0}]
          ]
        },
        "llm_processor_1": {
          "main": [
            [{"node": "chart_generator_1", "type": "main", "index": 0}]
          ]
        },
        "chart_generator_1": {
          "main": [
            [{"node": "report_formatter_1", "type": "main", "index": 0}]
          ]
        },
        "report_formatter_1": {
          "main": [
            [{"node": "export_handler_1", "type": "main", "index": 0}]
          ]
        },
        "export_handler_1": {
          "main": [
            [{"node": "notification_1", "type": "main", "index": 0}]
          ]
        }
      },
      "settings": {
        "executionOrder": "v1"
      }
    }
  },
  {
    id: 'flow-2',
    name: '客户反馈智能分析',
    description: '实时监控客户反馈系统，使用AI进行情感分析和分类，自动分配给相应的客服团队，并生成分析报告。',
    category: 'data_processing',
    createdAt: '2025-08-10',
    updatedAt: '2025-09-18',
    nodes: 12,
    active: true,
    jsonConfig: {
      "nodes": [
        {"id": "1", "type": "webhook", "name": "反馈接收器"},
        {"id": "2", "type": "ai", "name": "情感分析", "model": "sentiment-analysis"},
        {"id": "3", "type": "classifier", "name": "问题分类"},
        {"id": "4", "type": "router", "name": "路由分配"},
        {"id": "5", "type": "notification", "name": "团队通知"}
      ]
    }
  },
  {
    id: 'flow-3',
    name: 'API集成同步流程',
    description: '将多个第三方API数据源进行整合，定期同步到内部系统，包含数据验证、错误处理和重试机制。',
    category: 'integration',
    createdAt: '2025-07-20',
    updatedAt: '2025-09-15',
    nodes: 15,
    active: false,
    jsonConfig: {
      "nodes": [
        {"id": "1", "type": "http", "name": "API调用", "method": "GET"},
        {"id": "2", "type": "validator", "name": "数据验证"},
        {"id": "3", "type": "transformer", "name": "格式转换"},
        {"id": "4", "type": "database", "name": "数据存储"},
        {"id": "5", "type": "error_handler", "name": "错误处理"}
      ]
    }
  }
];

interface FlowsSectionProps {
  isMobile?: boolean;
}

const FlowsSection: React.FC<FlowsSectionProps> = ({ isMobile = false }) => {
  const [flows] = useState<Flow[]>(mockFlows);
  const [selectedFlow, setSelectedFlow] = useState<Flow | null>(null);
  const [showJsonModal, setShowJsonModal] = useState(false);

  const getCategoryColor = (_category: Flow['category']) => {
    return 'bg-[var(--accent)] text-[var(--foreground)] opacity-70';
  };

  const getCategoryLabel = (category: Flow['category']) => {
    switch (category) {
      case 'automation':
        return '自动化';
      case 'data_processing':
        return '数据处理';
      case 'integration':
        return '集成';
      case 'notification':
        return '通知';
      default:
        return category;
    }
  };

  // Mobile layout
  if (isMobile) {
    return (
      <div className="pb-4">
        {/* Mobile Header */}
        <div className="mb-4">
          <h2 className="text-xl font-bold text-[var(--foreground)] mb-2">Flows 工作流</h2>
          <p className="text-xs text-[var(--foreground)] opacity-70 leading-relaxed">
            管理您的自动化工作流程，通过预定义的流程编排实现复杂任务的自动化执行
          </p>
        </div>

        {/* Mobile Create Button */}
        <button className="w-full mb-4 px-4 py-3 bg-[var(--foreground)] text-[var(--background)] rounded-full font-medium flex items-center justify-center gap-2">
          <PlusIcon className="w-4 h-4" />
          创建新流程
        </button>

        {/* Mobile Flow Cards */}
        <div className="space-y-4">
          {flows.map((flow) => (
            <div
              key={flow.id}
              className="bg-[var(--card)] border border-[var(--border)] rounded-2xl p-4"
            >
              {/* Flow Header */}
              <div className="mb-3">
                <div className="flex items-start justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <CpuChipIcon className="w-5 h-5 text-[var(--foreground)] opacity-70 flex-shrink-0" />
                    <h3 className="text-base font-semibold text-[var(--foreground)] line-clamp-1">
                      {flow.name}
                    </h3>
                  </div>
                </div>
                
                {/* Status Tags */}
                <div className="flex items-center gap-2 mb-2">
                  <span className={`px-2 py-0.5 text-[10px] rounded-full ${getCategoryColor(flow.category)}`}>
                    {getCategoryLabel(flow.category)}
                  </span>
                  {flow.active ? (
                    <span className="px-2 py-0.5 text-[10px] rounded-full bg-green-500/20 text-green-500">
                      运行中
                    </span>
                  ) : (
                    <span className="px-2 py-0.5 text-[10px] rounded-full bg-[var(--accent)] text-[var(--foreground)] opacity-60">
                      已停止
                    </span>
                  )}
                </div>

                {/* Description */}
                <p className="text-xs text-[var(--foreground)] opacity-70 line-clamp-2 mb-2">
                  {flow.description}
                </p>

                {/* Metadata */}
                <div className="text-[10px] text-[var(--foreground)] opacity-50 space-y-0.5">
                  <div>包含 {flow.nodes} 个节点</div>
                  <div>创建于 {flow.createdAt} · 更新于 {flow.updatedAt}</div>
                </div>
              </div>

              {/* Mobile Action Buttons - Horizontal Scroll */}
              <div className="flex gap-2 overflow-x-auto pb-1 -mx-1 px-1 scrollbar-hide">
                <button className="flex-shrink-0 px-3 py-1.5 text-xs bg-[var(--accent)] text-[var(--foreground)] rounded-lg flex items-center gap-1.5 whitespace-nowrap">
                  <PlayIcon className="w-3.5 h-3.5" />
                  执行
                </button>
                <button className="flex-shrink-0 px-3 py-1.5 text-xs bg-[var(--accent)] text-[var(--foreground)] opacity-70 rounded-lg flex items-center gap-1.5 whitespace-nowrap">
                  <PencilIcon className="w-3.5 h-3.5" />
                  编辑
                </button>
                <button 
                  onClick={() => {
                    setSelectedFlow(flow);
                    setShowJsonModal(true);
                  }}
                  className="flex-shrink-0 px-3 py-1.5 text-xs bg-[var(--accent)] text-[var(--foreground)] opacity-70 rounded-lg flex items-center gap-1.5 whitespace-nowrap"
                >
                  <ArrowDownTrayIcon className="w-3.5 h-3.5" />
                  导出配置
                </button>
                <button className="flex-shrink-0 px-3 py-1.5 text-xs bg-[var(--accent)] text-[var(--foreground)] opacity-70 rounded-lg flex items-center gap-1.5 whitespace-nowrap">
                  <DocumentDuplicateIcon className="w-3.5 h-3.5" />
                  复制
                </button>
                <button className="flex-shrink-0 px-3 py-1.5 text-xs text-red-400 rounded-lg flex items-center gap-1.5 whitespace-nowrap">
                  <TrashIcon className="w-3.5 h-3.5" />
                  删除
                </button>
              </div>
            </div>
          ))}
        </div>

        {/* Mobile Modal */}
        {showJsonModal && selectedFlow && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
            <div className="bg-[var(--background)] border border-[var(--border)] rounded-2xl w-full max-w-sm max-h-[70vh] overflow-hidden">
              <div className="p-4 border-b border-[var(--border)]">
                <h3 className="text-base font-semibold text-[var(--foreground)]">
                  流程配置
                </h3>
                <p className="text-xs text-[var(--foreground)] opacity-60 mt-1">
                  {selectedFlow.name}
                </p>
              </div>
              <div className="p-4 overflow-y-auto max-h-[40vh]">
                <pre className="bg-[var(--accent)] p-3 rounded-lg overflow-x-auto text-[10px]">
                  <code className="text-[var(--foreground)]">{JSON.stringify(selectedFlow.jsonConfig, null, 2)}</code>
                </pre>
              </div>
              <div className="p-4 border-t border-[var(--border)] flex gap-2">
                <button
                  onClick={() => {
                    navigator.clipboard.writeText(JSON.stringify(selectedFlow.jsonConfig, null, 2));
                  }}
                  className="flex-1 px-3 py-2 bg-[var(--foreground)] text-[var(--background)] rounded-lg text-sm font-medium"
                >
                  复制
                </button>
                <button
                  onClick={() => setShowJsonModal(false)}
                  className="flex-1 px-3 py-2 bg-[var(--accent)] text-[var(--foreground)] rounded-lg text-sm"
                >
                  关闭
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    );
  }

  // Desktop layout (original)
  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold text-[var(--foreground)] mb-2">Flows 工作流</h2>
          <p className="text-sm text-[var(--foreground)] opacity-70">
            管理您的自动化工作流程，通过预定义的流程编排实现复杂任务的自动化执行
          </p>
        </div>
        <button className="px-6 py-3 bg-[var(--foreground)] text-[var(--background)] rounded-lg font-medium border-2 border-[var(--background)] hover:opacity-90 transition-opacity flex items-center gap-2">
          <PlusIcon className="w-5 h-5" />
          创建新流程
        </button>
      </div>

      <div className="grid gap-4">
        {flows.map((flow) => (
          <div
            key={flow.id}
            className="bg-[var(--card)] border border-[var(--border)] rounded-lg p-6 hover:border-[var(--foreground)]/20 transition-all"
          >
            <div className="flex items-start justify-between mb-4">
              <div className="flex-1">
                <div className="flex items-center gap-3 mb-2">
                  <CpuChipIcon className="w-6 h-6 text-[var(--foreground)] opacity-70" />
                  <h3 className="text-lg font-semibold text-[var(--foreground)]">{flow.name}</h3>
                  <span className={`px-2 py-1 text-xs rounded-full ${getCategoryColor(flow.category)}`}>
                    {getCategoryLabel(flow.category)}
                  </span>
                  {flow.active && (
                    <span className="px-2 py-1 text-xs rounded-full bg-[var(--accent)] text-[var(--foreground)]">
                      运行中
                    </span>
                  )}
                  {!flow.active && (
                    <span className="px-2 py-1 text-xs rounded-full bg-[var(--accent)] text-[var(--foreground)] opacity-60">
                      已停止
                    </span>
                  )}
                </div>
                <p className="text-sm text-[var(--foreground)] opacity-70 mb-3">
                  {flow.description}
                </p>
                <div className="flex items-center gap-4 text-xs text-[var(--foreground)] opacity-60">
                  <span>包含 {flow.nodes} 个节点</span>
                  <span>创建于 {flow.createdAt}</span>
                  <span>更新于 {flow.updatedAt}</span>
                </div>
              </div>
            </div>

            <div className="flex items-center gap-2 pt-4 border-t border-[var(--border)]">
              <button className="px-3 py-1.5 text-sm bg-[var(--accent)] text-[var(--foreground)] rounded-md hover:opacity-80 transition-opacity flex items-center gap-1.5">
                <PlayIcon className="w-4 h-4" />
                {flow.active ? '执行' : '运行'}
              </button>
              <button className="px-3 py-1.5 text-sm bg-[var(--accent)] text-[var(--foreground)] opacity-70 hover:opacity-100 rounded-md transition-opacity flex items-center gap-1.5">
                <PencilIcon className="w-4 h-4" />
                编辑
              </button>
              <button 
                onClick={() => {
                  setSelectedFlow(flow);
                  setShowJsonModal(true);
                }}
                className="px-3 py-1.5 text-sm bg-[var(--accent)] text-[var(--foreground)] opacity-70 hover:opacity-100 rounded-md transition-opacity flex items-center gap-1.5"
              >
                <ArrowDownTrayIcon className="w-4 h-4" />
                导出配置
              </button>
              <button className="px-3 py-1.5 text-sm bg-[var(--accent)] text-[var(--foreground)] opacity-70 hover:opacity-100 rounded-md transition-opacity flex items-center gap-1.5">
                <DocumentDuplicateIcon className="w-4 h-4" />
                复制
              </button>
              <button className="px-3 py-1.5 text-sm text-red-400 hover:text-red-500 rounded-md transition-opacity flex items-center gap-1.5">
                <TrashIcon className="w-4 h-4" />
                删除
              </button>
            </div>
          </div>
        ))}
      </div>

      {showJsonModal && selectedFlow && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-[var(--background)] border border-[var(--border)] rounded-lg max-w-2xl w-full max-h-[80vh] overflow-hidden">
            <div className="p-6 border-b border-[var(--border)]">
              <h3 className="text-lg font-semibold text-[var(--foreground)]">
                {selectedFlow.name} - 流程配置
              </h3>
            </div>
            <div className="p-6 overflow-y-auto max-h-[60vh]">
              <pre className="bg-[var(--accent)] p-4 rounded-lg overflow-x-auto text-sm">
                <code className="text-[var(--foreground)]">{JSON.stringify(selectedFlow.jsonConfig, null, 2)}</code>
              </pre>
            </div>
            <div className="p-6 border-t border-[var(--border)] flex justify-end gap-3">
              <button
                onClick={() => {
                  navigator.clipboard.writeText(JSON.stringify(selectedFlow.jsonConfig, null, 2));
                }}
                className="px-4 py-2 bg-[var(--foreground)] text-[var(--background)] rounded-lg font-medium hover:opacity-90 transition-opacity"
              >
                复制到剪贴板
              </button>
              <button
                onClick={() => setShowJsonModal(false)}
                className="px-4 py-2 bg-[var(--accent)] text-[var(--foreground)] rounded-lg hover:opacity-80 transition-opacity"
              >
                关闭
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
};

export default FlowsSection;