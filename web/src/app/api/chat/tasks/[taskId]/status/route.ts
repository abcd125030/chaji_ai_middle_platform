/**
 * 任务状态查询 API 代理
 * 转发到后端的任务状态检查接口
 */

import { NextRequest } from 'next/server';
import { proxyToBackend, handleOptions } from '@/lib/backend-proxy';

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ taskId: string }> }
) {
  const { taskId } = await params;
  return proxyToBackend(request, `/webapps/chat/tasks/${taskId}/status/`);
}

export async function OPTIONS() {
  return handleOptions();
}