import { NextRequest } from 'next/server';
import { proxyToBackend } from '@/lib/backend-proxy';

export async function POST(request: NextRequest) {
  // 直接代理到后端的激活码验证接口
  return proxyToBackend(request, '/activation/verify/');
}