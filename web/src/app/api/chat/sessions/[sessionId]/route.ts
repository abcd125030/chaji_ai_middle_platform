/**
 * 单个聊天会话 API 代理
 * 转发到后端的会话详情接口
 */

import { NextRequest } from 'next/server';
import { proxyToBackend, handleOptions } from '@/lib/backend-proxy';

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ sessionId: string }> }
) {
  const { sessionId } = await params;
  return proxyToBackend(request, `/webapps/chat/sessions/${sessionId}/`);
}

export async function PUT(
  request: NextRequest,
  { params }: { params: Promise<{ sessionId: string }> }
) {
  const { sessionId } = await params;
  return proxyToBackend(request, `/webapps/chat/sessions/${sessionId}/`);
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ sessionId: string }> }
) {
  const { sessionId } = await params;
  return proxyToBackend(request, `/webapps/chat/sessions/${sessionId}/`);
}

export async function OPTIONS() {
  return handleOptions();
}