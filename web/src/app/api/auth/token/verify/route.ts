/**
 * Token 验证 API 代理
 * 转发到后端的 token 验证接口
 */

import { NextRequest } from 'next/server';
import { proxyToBackend, handleOptions } from '@/lib/backend-proxy';

export async function POST(request: NextRequest) {
  return proxyToBackend(request, '/auth/token/verify/');
}

export async function OPTIONS() {
  return handleOptions();
}