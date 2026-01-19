/**
 * 通用后端 API 代理
 * 将所有 /api/backend/* 请求转发到后端服务
 * 使用方式：将原本的后端 API 路径前加上 /api/backend
 */

import { NextRequest } from 'next/server';
import { proxyToBackend, handleOptions } from '@/lib/backend-proxy';

// 辅助函数：构建路径（Django REST Framework 需要尾部斜杠）
function buildPath(pathArray: string[]): string {
  let path = `/${pathArray.join('/')}`;
  // 确保路径以斜杠结尾（Django APPEND_SLASH 设置要求）
  if (!path.endsWith('/')) {
    path += '/';
  }
  return path;
}

// 处理所有 HTTP 方法
export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const resolvedParams = await params;
  const path = buildPath(resolvedParams.path);
  return proxyToBackend(request, path);
}

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const resolvedParams = await params;
  const path = buildPath(resolvedParams.path);
  return proxyToBackend(request, path);
}

export async function PUT(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const resolvedParams = await params;
  const path = buildPath(resolvedParams.path);
  return proxyToBackend(request, path);
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const resolvedParams = await params;
  const path = buildPath(resolvedParams.path);
  return proxyToBackend(request, path);
}

export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const resolvedParams = await params;
  const path = buildPath(resolvedParams.path);
  return proxyToBackend(request, path);
}

export async function OPTIONS() {
  return handleOptions();
}