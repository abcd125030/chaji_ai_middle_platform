// 任务步骤相关类型定义
export interface TaskStep {
  node_name: string;
  action?: string;
  tool_name?: string;
  status?: 'pending' | 'running' | 'completed' | 'failed';
  timestamp?: string;
}

// 任务状态类型
export type TaskStatus = 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED';

// 任务响应数据类型
export interface TaskResponse {
  task_id: string;
  status: TaskStatus;
  steps?: TaskStep[];
  output_data?: {
    final_conclusion?: string;
    error?: string;
  };
}

// API 错误响应类型
export interface APIErrorResponse {
  detail?: string;
  error?: string;
  message?: string;
}