/**
 * 检查未完成任务 API 代理
 * 转发到后端的任务检查接口
 */

import { NextRequest } from 'next/server';
import { proxyToBackend, handleOptions } from '@/lib/backend-proxy';

export async function POST(request: NextRequest) {
  return proxyToBackend(request, '/webapps/chat/check-incomplete-tasks/');
}

export async function OPTIONS() {
  return handleOptions();
}