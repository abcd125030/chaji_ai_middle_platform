import { NextRequest, NextResponse } from 'next/server';
import { proxyToBackend } from '@/lib/backend-proxy';

export async function POST(request: NextRequest) {
  try {
    // 代理到后端的 Google 回调端点
    return proxyToBackend(request, '/auth/google/callback/');
  } catch (error) {
    console.error('Google callback proxy error:', error);
    return NextResponse.json(
      { error: 'Failed to process Google callback' },
      { status: 500 }
    );
  }
}