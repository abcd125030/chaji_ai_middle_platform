/**
 * 飞书登录回调 API 代理
 * 处理飞书登录回调并转发到后端
 */

import { NextRequest } from 'next/server';
import { proxyToBackend, handleOptions } from '@/lib/backend-proxy';

export async function POST(request: NextRequest) {
  return proxyToBackend(request, '/auth/feishu/callback/');
}

export async function OPTIONS() {
  return handleOptions();
}