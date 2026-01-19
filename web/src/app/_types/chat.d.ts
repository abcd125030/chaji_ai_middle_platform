// 聊天相关类型定义
import { TaskStep } from '@/lib/sessionManager';

/**
 * JWT Payload 接口定义
 */
export interface JwtPayload {
  user_id: string; // 用户 ID
}

/**
 * 聊天消息接口
 */
export interface Message {
  role: 'user' | 'assistant'; // 消息角色
  content: string; // 消息内容
  files?: Array<{ name: string; size: number; type: string }>; // 文件信息
  taskId?: string; // 关联的任务ID
  taskSteps?: TaskStep[]; // 任务步骤详情
  finalWebSearchResults?: WebSearchResult[]; // 最终网页搜索结果
  timestamp: Date; // 消息时间戳
}

/**
 * 网页搜索结果接口
 */
export interface WebSearchResult {
  title: string; // 结果标题
  url: string; // 结果URL
  snippet?: string; // 摘要片段
  favicon?: string; // 网站图标
}