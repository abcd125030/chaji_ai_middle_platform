/**
 * 聊天消息 API 代理
 * 转发到后端的消息管理接口
 * 支持直接SSE流转发
 */

import { NextRequest, NextResponse } from 'next/server';
import { proxyToBackend, handleOptions } from '@/lib/backend-proxy';
import { logger } from '@/lib/server-logger';


export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ sessionId: string }> }
) {
  const { sessionId } = await params;
  return proxyToBackend(request, `/webapps/chat/sessions/${sessionId}/messages/`);
}

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ sessionId: string }> }
) {
  try {
    const { sessionId } = await params;
    logger.info(`[Messages Route] POST request received for session ${sessionId}`);
    
    // 检查是否需要 SSE 流式响应
    const acceptHeader = request.headers.get('accept');
    const isSSERequest = acceptHeader?.includes('text/event-stream');
    logger.info(`[Messages Route] SSE request: ${isSSERequest}, Accept header: ${acceptHeader}`);
  
  if (isSSERequest) {
    logger.info(`[Messages Route] SSE request for session ${sessionId}`);
    
    // 读取 JSON 请求体
    logger.info('[Messages Route] Parsing JSON body...');
    const requestBody = await request.json();
    logger.info(`[Messages Route] Request body keys: ${Object.keys(requestBody).join(', ')}`);
    
    // 检查是否是重连请求
    const isReconnect = requestBody.message === '[RECONNECT]' && requestBody.task_id;
    logger.info(`[Messages Route] Is reconnect: ${isReconnect}`);
    
    const backendUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:6066/api';
    
    // 准备认证头
    const authHeaders = new Headers();
    // 复制认证相关的header
    const authToken = request.headers.get('authorization');
    if (authToken) {
      authHeaders.set('authorization', authToken);
    }
    const cookie = request.headers.get('cookie');
    if (cookie) {
      authHeaders.set('cookie', cookie);
    }
    
    if (isReconnect) {
      // 重连：直接连接到SSE流
      const taskId = requestBody.task_id;
      const sseUrl = `${backendUrl}/webapps/chat/tasks/${taskId}/stream/?reconnect=true`;
      logger.info(`[Messages Route] Reconnecting to SSE stream: ${sseUrl}`);
      
      // 建立SSE连接
      const sseResponse = await fetch(sseUrl, {
        headers: {
          'Accept': 'text/event-stream',
          ...Object.fromEntries(authHeaders.entries())
        }
      });
      
      if (!sseResponse.ok) {
        const errorText = await sseResponse.text();
        return new NextResponse(errorText, {
          status: sseResponse.status,
          headers: { 'Content-Type': 'application/json' }
        });
      }
      
      // 转发SSE流
      return new Response(sseResponse.body, {
        headers: {
          'Content-Type': 'text/event-stream',
          'Cache-Control': 'no-cache',
          'Connection': 'keep-alive',
        },
      });
    } else {
      // 新消息：先创建任务，再建立SSE
      
      // 1. 发送消息到后端（请求JSON响应，不是SSE）
      const createUrl = `${backendUrl}/webapps/chat/sessions/${sessionId}/messages/`;
      logger.info(`[Messages Route] Creating task: ${createUrl}`);
      
      const createHeaders = new Headers(authHeaders);
      createHeaders.set('accept', 'application/json');  // 请求JSON响应
      createHeaders.set('content-type', 'application/json');
      
      const createResponse = await fetch(createUrl, {
        method: 'POST',
        headers: createHeaders,
        body: JSON.stringify(requestBody),
      });
      
      if (!createResponse.ok) {
        const errorText = await createResponse.text();
        return new NextResponse(errorText, {
          status: createResponse.status,
          headers: { 'Content-Type': 'application/json' }
        });
      }
      
      // 2. 获取task_id
      const taskData = await createResponse.json();
      const taskId = taskData.task_id;
      const sessionIdFromResponse = taskData.session_id;
      
      logger.info(`[Messages Route] Task created: ${taskId}`);
      
      // 3. 建立SSE连接到新的stream接口
      const sseUrl = `${backendUrl}/webapps/chat/tasks/${taskId}/stream/`;
      logger.info(`[Messages Route] Connecting to SSE stream: ${sseUrl}`);
      
      const sseResponse = await fetch(sseUrl, {
        headers: {
          'Accept': 'text/event-stream',
          ...Object.fromEntries(authHeaders.entries())
        }
      });
      
      if (!sseResponse.ok) {
        const errorText = await sseResponse.text();
        return new NextResponse(
          JSON.stringify({ 
            error: 'Failed to establish SSE connection',
            details: errorText
          }),
          { status: 502, headers: { 'Content-Type': 'application/json' } }
        );
      }
      
      // 4. 创建转发流
      const stream = new ReadableStream({
        async start(controller) {
          const encoder = new TextEncoder();
          const decoder = new TextDecoder();
          
          // 先发送task_started事件
          controller.enqueue(encoder.encode(`data: ${JSON.stringify({
            type: 'task_started',
            taskId: taskId,
            task_id: taskId,
            sessionId: sessionIdFromResponse || sessionId,
            session_id: sessionIdFromResponse || sessionId
          })}\n\n`));
          
          // 转发后端SSE流
          const reader = sseResponse.body?.getReader();
          if (!reader) {
            controller.close();
            return;
          }
          
          // 设置超时（5分钟）
          const timeout = setTimeout(() => {
            try {
              controller.enqueue(encoder.encode(`data: ${JSON.stringify({
                type: 'timeout',
                message: '页面等待超时，任务可能仍在后台执行中'
              })}\n\n`));
              controller.close();
              reader.cancel();
            } catch (e) {
              logger.error('Failed to send timeout message:', e);
            }
          }, 5 * 60 * 1000);
          
          try {
            while (true) {
              const { done, value } = await reader.read();
              if (done) {
                clearTimeout(timeout);
                controller.close();
                break;
              }
              
              // 直接转发后端的SSE数据
              controller.enqueue(value);
              
              // 解析SSE事件以进行日志记录
              const chunk = decoder.decode(value, { stream: true });
              if (chunk.includes('data: ')) {
                const lines = chunk.split('\n');
                for (const line of lines) {
                  if (line.startsWith('data: ')) {
                    try {
                      const eventData = JSON.parse(line.substring(6));
                      logger.info(`[Messages Route] SSE event: ${eventData.type}`);
                    } catch {
                      // 忽略解析错误
                    }
                  }
                }
              }
            }
          } catch (error) {
            logger.error('[Messages Route] Error reading SSE stream:', error);
            clearTimeout(timeout);
            try {
              controller.enqueue(encoder.encode(`data: ${JSON.stringify({
                type: 'error',
                message: 'Stream connection lost'
              })}\n\n`));
            } catch {
              // 忽略
            }
            controller.close();
          }
          
          // 监听请求中断
          request.signal.addEventListener('abort', () => {
            clearTimeout(timeout);
            reader.cancel();
            controller.close();
          });
        }
      });
      
      return new Response(stream, {
        headers: {
          'Content-Type': 'text/event-stream',
          'Cache-Control': 'no-cache',
          'Connection': 'keep-alive',
        },
      });
    }
  } else {
    // 普通请求，不需要回调地址，直接转发
    logger.info(`[Messages Route] Non-SSE request for session ${sessionId}`);
    const requestBody = await request.json();
    
    // 克隆请求头
    const headers = new Headers(request.headers);
    headers.delete('host');
    headers.delete('x-forwarded-host');
    headers.delete('x-forwarded-proto');
    headers.delete('x-forwarded-port');
    headers.delete('content-length');
    headers.set('content-type', 'application/json');
    
    // 直接转发到后端
    const backendUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:6066/api';
    const backendResponse = await fetch(`${backendUrl}/webapps/chat/sessions/${sessionId}/messages/`, {
      method: 'POST',
      headers: headers,
      body: JSON.stringify(requestBody) // 直接转发，不修改
    });
    
    // 返回后端响应
    const responseBody = await backendResponse.text();
    return new NextResponse(responseBody, {
      status: backendResponse.status,
      headers: {
        'Content-Type': backendResponse.headers.get('content-type') || 'application/json'
      }
    });
  }
  } catch (error) {
    logger.error('[Messages Route] Error in POST handler:', error);
    return new NextResponse(
      JSON.stringify({ 
        error: 'Internal server error', 
        message: error instanceof Error ? error.message : 'Unknown error',
        details: error instanceof Error ? error.stack : undefined
      }),
      { 
        status: 500,
        headers: { 'Content-Type': 'application/json' }
      }
    );
  }
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ sessionId: string }> }
) {
  const { sessionId } = await params;
  return proxyToBackend(request, `/webapps/chat/sessions/${sessionId}/messages/`);
}

export async function OPTIONS() {
  return handleOptions();
}