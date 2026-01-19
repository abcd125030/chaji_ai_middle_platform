/**
 * 后端 API 代理工具
 * 用于将 web 端的 API 请求转发到后端服务
 */

import { NextRequest, NextResponse } from 'next/server';
import { logger } from './server-logger';

// 获取后端 API 基础 URL
export function getBackendUrl(): string {
  return process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:6066/api';
}

/**
 * 代理请求到后端
 * @param request - Next.js 请求对象
 * @param path - API 路径（不包含基础 URL）
 * @param options - 额外的 fetch 选项
 */
export async function proxyToBackend(
  request: NextRequest,
  path: string,
  options: RequestInit = {}
): Promise<NextResponse> {
  const backendUrl = getBackendUrl();
  
  // 获取查询参数
  const searchParams = request.nextUrl.searchParams;
  const queryString = searchParams.toString();
  const url = queryString ? `${backendUrl}${path}?${queryString}` : `${backendUrl}${path}`;

  // 获取请求头
  const headers = new Headers(request.headers);
  
  // 移除 Next.js 特有的头和 content-length（让 fetch 自动计算）
  headers.delete('host');
  headers.delete('x-forwarded-host');
  headers.delete('x-forwarded-proto');
  headers.delete('x-forwarded-port');
  headers.delete('content-length');
  
  // 确保 Content-Type 正确
  if (!headers.get('content-type') && request.method !== 'GET' && request.method !== 'HEAD') {
    headers.set('content-type', 'application/json');
  }

  // 创建 AbortController 用于超时控制
  const controller = new AbortController();
  // 根据不同的请求类型设置不同的超时时间
  let timeoutMs = 60000; // 默认60秒
  if (path.includes('/messages')) {
    timeoutMs = 120000; // 消息接口120秒
  } else if (path.includes('/extractor/upload') || path.includes('/upload')) {
    timeoutMs = 180000; // 文件上传接口180秒
  } else if (path.includes('/generate')) {
    timeoutMs = 300000; // AI生成接口300秒
  }
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  // 构建请求选项
  const fetchOptions: RequestInit = {
    method: request.method,
    headers,
    signal: controller.signal, // 添加 abort signal
    ...options,
  };

  // 处理请求体
  if (request.method !== 'GET' && request.method !== 'HEAD') {
    try {
      const contentType = headers.get('content-type') || '';
      
      if (contentType.includes('application/json')) {
        // 对于 JSON，直接传递原始文本，避免不必要的解析和序列化
        // 这样可以更高效地处理包含 base64 的大 JSON 请求
        fetchOptions.body = await request.text();
      } else if (contentType.includes('multipart/form-data')) {
        // 对于 multipart/form-data，需要特殊处理
        try {
          const formData = await request.formData();
          fetchOptions.body = formData;
          // 删除 content-type，让 fetch 自动设置边界
          headers.delete('content-type');
        } catch (error) {
          logger.error('Error parsing FormData:', error);
          // 如果 FormData 解析失败，返回错误
          return NextResponse.json(
            {
              error: 'Failed to parse FormData',
              message: error instanceof Error ? error.message : 'Unknown error',
            },
            { status: 400 }
          );
        }
      } else {
        // 其他类型，直接传递原始文本
        fetchOptions.body = await request.text();
      }
    } catch (error) {
      logger.error('Error parsing request body:', error);
      // 如果解析失败，尝试获取原始文本
      try {
        fetchOptions.body = await request.text();
      } catch {
        // 忽略错误，不设置 body
      }
    }
  }

  try {
    // 调试日志
    logger.info('========== Backend Proxy Start ==========');
    logger.info('Proxying request to:', url);
    logger.info('Request method:', fetchOptions.method);
    logger.info('Timeout:', timeoutMs + 'ms');
    logger.info('Content-Type:', headers.get('content-type'));

    // 如果是 FormData，记录文件信息
    if (fetchOptions.body instanceof FormData) {
      const entries = Array.from(fetchOptions.body.entries());
      logger.info('FormData entries count:', entries.length);
      entries.forEach(([key, value]) => {
        if (value instanceof File) {
          logger.info(`FormData file: ${key} = ${value.name} (${value.size} bytes)`);
        } else {
          logger.info(`FormData field: ${key} = ${String(value).substring(0, 100)}`);
        }
      });
    } else if (typeof fetchOptions.body === 'string') {
      const bodySize = fetchOptions.body.length;
      logger.info('Request body size:', bodySize, 'bytes (', (bodySize / 1024).toFixed(2), 'KB)');
    }

    logger.info('Sending request to backend...');
    const startTime = Date.now();

    // 发送请求到后端
    const response = await fetch(url, fetchOptions);

    const duration = Date.now() - startTime;
    logger.info('Backend response received in', duration, 'ms');
    
    // 清除超时定时器
    clearTimeout(timeoutId);

    // 获取响应体
    const responseHeaders = new Headers(response.headers);
    
    // 移除 Content-Encoding 和 Content-Length 头
    // fetch 自动处理解压，内容长度会改变
    responseHeaders.delete('content-encoding');
    responseHeaders.delete('content-length');
    
    // 添加 CORS 头（如果需要）
    responseHeaders.set('Access-Control-Allow-Origin', '*');
    responseHeaders.set('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
    responseHeaders.set('Access-Control-Allow-Headers', 'Content-Type, Authorization');

    // 处理 204 No Content 响应
    if (response.status === 204) {
      return new NextResponse(null, {
        status: 204,
        headers: responseHeaders,
      });
    }
    
    // 根据响应类型处理响应体
    const contentType = response.headers.get('content-type') || '';
    
    if (contentType.includes('application/json')) {
      const data = await response.json();
      return NextResponse.json(data, {
        status: response.status,
        headers: responseHeaders,
      });
    } else if (contentType.includes('text/')) {
      const text = await response.text();
      return new NextResponse(text, {
        status: response.status,
        headers: responseHeaders,
      });
    } else {
      // 对于其他类型（如二进制数据），直接传递
      const buffer = await response.arrayBuffer();
      return new NextResponse(buffer, {
        status: response.status,
        headers: responseHeaders,
      });
    }
  } catch (error) {
    // 清除超时定时器
    clearTimeout(timeoutId);

    // 判断是否为超时错误
    if (error instanceof Error && error.name === 'AbortError') {
      logger.error('========== Backend Proxy TIMEOUT ==========');
      logger.error(`Request timeout after ${timeoutMs}ms:`, url);
      return NextResponse.json(
        {
          error: 'Request timeout',
          message: `请求超时（${timeoutMs/1000}秒）。请检查网络连接或稍后重试。`,
          timeout: true,
        },
        { status: 504 } // Gateway Timeout
      );
    }

    logger.error('========== Backend Proxy ERROR ==========');
    logger.error('Proxy error:', error);
    logger.error('Error name:', error instanceof Error ? error.name : 'Unknown');
    logger.error('Error message:', error instanceof Error ? error.message : String(error));

    // 返回错误响应
    return NextResponse.json(
      {
        error: 'Proxy request failed',
        message: error instanceof Error ? error.message : 'Unknown error',
      },
      { status: 500 }
    );
  }
}

/**
 * 处理 OPTIONS 预检请求
 */
export function handleOptions(): NextResponse {
  return new NextResponse(null, {
    status: 200,
    headers: {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type, Authorization',
      'Access-Control-Max-Age': '86400',
    },
  });
}

/**
 * 代理 SSE (Server-Sent Events) 流式请求到后端
 * @param request - Next.js 请求对象
 * @param path - API 路径（不包含基础 URL）
 * @param options - 额外的 fetch 选项
 */
export async function proxyStreamToBackend(
  request: NextRequest,
  path: string,
  options: RequestInit = {}
): Promise<Response> {
  const backendUrl = getBackendUrl();
  
  // 获取查询参数
  const searchParams = request.nextUrl.searchParams;
  const queryString = searchParams.toString();
  const url = queryString ? `${backendUrl}${path}?${queryString}` : `${backendUrl}${path}`;

  // 获取请求头
  const headers = new Headers(request.headers);
  
  // 移除 Next.js 特有的头和 content-length（让 fetch 自动计算）
  headers.delete('host');
  headers.delete('x-forwarded-host');
  headers.delete('x-forwarded-proto');
  headers.delete('x-forwarded-port');
  headers.delete('content-length');

  // 创建 AbortController 用于超时控制
  const controller = new AbortController();
  // SSE流式请求使用更长的超时时间（5分钟）
  const timeoutMs = 300000; // 300秒
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  // 构建请求选项
  const fetchOptions: RequestInit = {
    method: request.method,
    headers,
    signal: controller.signal, // 添加 abort signal
    ...options,
  };

  // 处理请求体
  if (request.method !== 'GET' && request.method !== 'HEAD') {
    try {
      const contentType = headers.get('content-type') || '';
      
      if (contentType.includes('application/json')) {
        const body = await request.json();
        fetchOptions.body = JSON.stringify(body);
      } else {
        fetchOptions.body = await request.text();
      }
    } catch (error) {
      logger.error('Error parsing request body:', error);
    }
  }

  try {
    // 发送请求到后端
    const response = await fetch(url, fetchOptions);
    
    // 清除超时定时器
    clearTimeout(timeoutId);

    // 如果不是 SSE 响应，使用普通代理
    const contentType = response.headers.get('content-type') || '';
    if (!contentType.includes('text/event-stream')) {
      return proxyToBackend(request, path, options);
    }

    // 创建 TransformStream 来转发 SSE 数据
    const stream = new ReadableStream({
      async start(controller) {
        const reader = response.body?.getReader();
        if (!reader) {
          controller.close();
          return;
        }

        try {
          while (true) {
            const { done, value } = await reader.read();
            if (done) {
              controller.close();
              break;
            }
            controller.enqueue(value);
          }
        } catch (error) {
          logger.error('Stream error:', error);
          controller.error(error);
        }
      },
    });

    // 返回流式响应
    return new Response(stream, {
      status: response.status,
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'Access-Control-Allow-Origin': '*',
      },
    });
  } catch (error) {
    // 清除超时定时器
    clearTimeout(timeoutId);
    
    // 判断是否为超时错误
    if (error instanceof Error && error.name === 'AbortError') {
      logger.error(`Stream request timeout after ${timeoutMs}ms:`, url);
      
      const encoder = new TextEncoder();
      const stream = new ReadableStream({
        start(controller) {
          controller.enqueue(encoder.encode(`data: ${JSON.stringify({
            error: 'Stream request timeout',
            message: `流式请求超时（${timeoutMs/1000}秒）。请检查网络连接或稍后重试。`,
            timeout: true,
          })}\n\n`));
          controller.close();
        },
      });

      return new Response(stream, {
        status: 504, // Gateway Timeout
        headers: {
          'Content-Type': 'text/event-stream',
          'Cache-Control': 'no-cache',
        },
      });
    }
    
    logger.error('Stream proxy error:', error);
    
    // 返回错误响应
    const encoder = new TextEncoder();
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(encoder.encode(`data: ${JSON.stringify({
          error: 'Stream proxy failed',
          message: error instanceof Error ? error.message : 'Unknown error',
        })}\n\n`));
        controller.close();
      },
    });

    return new Response(stream, {
      status: 500,
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
      },
    });
  }
}