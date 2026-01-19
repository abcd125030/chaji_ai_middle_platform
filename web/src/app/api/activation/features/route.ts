import { NextRequest } from 'next/server';
import { proxyToBackend } from '@/lib/backend-proxy';

export async function GET(request: NextRequest) {
  // 代理到后端获取用户已激活的功能列表
  return proxyToBackend(request, '/activation/features/');
}