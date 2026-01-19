import { proxyToBackend } from '@/lib/backend-proxy';
import { NextRequest } from 'next/server';
import { logger } from '@/lib/server-logger';

// 通配符路由，将所有 /api/webapps/moments/* 请求代理到后端
export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path: pathArray } = await params;
  const path = pathArray?.join('/') || '';
  // 保留原始URL的末尾斜杠
  const originalPath = request.nextUrl.pathname;
  const hasTrailingSlash = originalPath.endsWith('/');
  const finalPath = `/webapps/moments/${path}${hasTrailingSlash ? '/' : ''}`;

  logger.info('[Moments API Route] GET request:', originalPath, '-> finalPath:', finalPath);

  return proxyToBackend(request, finalPath);
}

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path: pathArray } = await params;
  const path = pathArray?.join('/') || '';

  const originalPath = request.nextUrl.pathname;

  // POST请求强制添加末尾斜杠（Django APPEND_SLASH要求）
  const finalPath = `/webapps/moments/${path}/`;

  logger.info('[Moments API Route] POST request:', originalPath, '-> finalPath:', finalPath);
  logger.info('[Moments API Route] Content-Type:', request.headers.get('content-type'));

  return proxyToBackend(request, finalPath);
}

export async function PUT(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path: pathArray } = await params;
  const path = pathArray?.join('/') || '';

  // PUT请求强制添加末尾斜杠（Django APPEND_SLASH要求）
  const finalPath = `/webapps/moments/${path}/`;

  return proxyToBackend(request, finalPath);
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path: pathArray } = await params;
  const path = pathArray?.join('/') || '';

  // DELETE请求强制添加末尾斜杠（Django APPEND_SLASH要求）
  const finalPath = `/webapps/moments/${path}/`;

  return proxyToBackend(request, finalPath);
}
