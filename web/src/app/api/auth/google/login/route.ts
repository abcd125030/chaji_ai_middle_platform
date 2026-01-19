import { NextRequest, NextResponse } from 'next/server';
import { proxyToBackend } from '@/lib/backend-proxy';

export async function GET(request: NextRequest) {
  try {
    // 代理到后端的 Google 登录端点
    return proxyToBackend(request, '/auth/google/login/');
  } catch (error) {
    console.error('Google login proxy error:', error);
    return NextResponse.json(
      { error: 'Failed to initiate Google login' },
      { status: 500 }
    );
  }
}