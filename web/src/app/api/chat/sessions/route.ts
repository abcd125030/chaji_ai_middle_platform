/**
 * 聊天会话 API 代理
 * 转发到后端的会话管理接口
 */

import { NextRequest } from 'next/server';
import { proxyToBackend, handleOptions } from '@/lib/backend-proxy';

export async function GET(request: NextRequest) {
  return proxyToBackend(request, '/webapps/chat/sessions/');
}

export async function POST(request: NextRequest) {
  return proxyToBackend(request, '/webapps/chat/sessions/');
}

export async function OPTIONS() {
  return handleOptions();
}