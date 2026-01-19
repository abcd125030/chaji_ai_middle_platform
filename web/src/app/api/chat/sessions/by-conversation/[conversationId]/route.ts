/**
 * 通过会话 ID 查找聊天会话 API 代理
 * 转发到后端的会话查找接口
 */

import { NextRequest } from 'next/server';
import { proxyToBackend, handleOptions } from '@/lib/backend-proxy';

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ conversationId: string }> }
) {
  const { conversationId } = await params;
  return proxyToBackend(request, `/webapps/chat/sessions/by-conversation/${conversationId}/`);
}

export async function OPTIONS() {
  return handleOptions();
}