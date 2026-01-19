import { NextRequest } from 'next/server';
import { proxyToBackend } from '@/lib/backend-proxy';

// POST /api/pagtive/generate - AI生成页面内容
export async function POST(request: NextRequest) {
  // 直接使用 proxyToBackend 转发请求到后端
  // proxyToBackend 会自动处理：
  // 1. 从环境变量读取后端URL (NEXT_PUBLIC_API_BASE_URL = http://127.0.0.1:6066/api)
  // 2. 保留所有请求头（包括Authorization）
  // 3. 转发请求体
  // 4. 返回后端响应
  // 
  // 注意：后端的完整路径是 /api/webapps/pagtive/generate/
  // 但 proxyToBackend 会拼接基础URL (http://127.0.0.1:6066/api) + 路径
  // 所以这里只需要传 /webapps/pagtive/generate/
  return proxyToBackend(request, '/webapps/pagtive/generate/');
}