/**
 * 飞书登录 API 代理
 * 转发到后端的飞书登录接口
 */

import { NextRequest, NextResponse } from 'next/server';
import { getBackendUrl } from '@/lib/backend-proxy';

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const redirectUri = searchParams.get('redirect_uri');
  
  // 构建后端登录 URL
  const backendUrl = getBackendUrl();
  const loginUrl = new URL(`${backendUrl}/auth/feishu/login`);
  
  if (redirectUri) {
    loginUrl.searchParams.set('redirect_uri', redirectUri);
  }

  // 重定向到后端登录页面
  return NextResponse.redirect(loginUrl.toString());
}