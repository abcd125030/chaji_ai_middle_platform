/**
 * 简化的认证请求工具
 * 替代复杂的 fetchWithAuth 实现
 */

// import { ResponseInterceptor } from './response-interceptor'; // Not used currently

// 动态导入 logger，仅在服务端使用
// eslint-disable-next-line @typescript-eslint/no-explicit-any
let logger: any = null;
if (typeof window === 'undefined') {
  // 仅在服务端导入
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  logger = require('./server-logger').logger;
}

/**
 * 获取认证头
 * @returns 包含 Authorization 头的对象，如果没有认证信息则返回空对象
 */
export function getAuthHeaders(): Record<string, string> {
  if (typeof window === 'undefined') return {};
  
  const auth = localStorage.getItem('auth');
  if (!auth) return {};
  
  try {
    const { access } = JSON.parse(auth);
    return access ? { 'Authorization': `Bearer ${access}` } : {};
  } catch {
    return {};
  }
}

/**
 * 带认证的 fetch 请求（支持重试）
 * @param url 请求 URL
 * @param options fetch 选项
 * @param retryCount 当前重试次数（内部使用）
 * @returns Promise<Response>
 */
export async function authFetch(
  url: string, 
  options: RequestInit = {},
  retryCount: number = 0
): Promise<Response> {
  const maxRetries = 0;  // 减少重试次数，避免过多请求
  const retryDelay = 1000; // 1秒延迟
  const isServerSide = typeof window === 'undefined';
  
  // 处理 basePath
  const basePath = process.env.NEXT_PUBLIC_BASE_PATH || '';
  const fullUrl = url.startsWith('http') ? url : `${basePath}${url}`;
  
  if (isServerSide && logger) {
    logger.debug(`authFetch - 请求 [重试 ${retryCount}/${maxRetries}]`, {
      url: fullUrl,
      method: options.method || 'GET',
      hasAuth: !!getAuthHeaders().Authorization
    });
  } else if (typeof window !== 'undefined') {
    console.info('【authFetch】请求 URL:', fullUrl);
    console.info('【authFetch】请求方法:', options.method || 'GET');
  }
  
  try {
    const controller = new AbortController();
    // 对于不同类型的接口，设置不同的超时时间
    // 注意：匹配完整的 API 路径，避免误判
    const isAIGeneration =
      fullUrl.includes('/api/presentation/generate') ||
      fullUrl.includes('/api/pagtive/generate') ||
      fullUrl.includes('/api/chat/sessions/') ||
      fullUrl.includes('/generate-outline');

    const isFileUpload =
      fullUrl.includes('/api/webapps/toolkit/extractor/upload') ||
      fullUrl.includes('/upload');

    // AI生成5分钟，文件上传3分钟，其他60秒
    let timeoutMs = 60000;
    if (isAIGeneration) {
      timeoutMs = 300000; // 5分钟
    } else if (isFileUpload) {
      timeoutMs = 180000; // 3分钟
    }
    
    const timeoutId = setTimeout(() => {
      // 某些浏览器需要提供 abort 原因
      const timeoutSecs = timeoutMs / 1000;
      const abortReason = new Error(`Request timeout after ${timeoutSecs}s`);
      controller.abort(abortReason);
      if (isServerSide && logger) {
        logger.warn(`authFetch - 请求超时 (${timeoutSecs}s)`, { url: fullUrl });
      }
    }, timeoutMs);
    
    const startTime = Date.now();
    // 检查是否是 FormData 请求
    const isFormData = options.body instanceof FormData;
    
    // 检查是否是大的 JSON 请求（可能包含 base64）
    let isLargeRequest = false;
    if (typeof options.body === 'string') {
      // 如果请求体是字符串（JSON），检查大小
      // keepalive 限制为 64KB
      isLargeRequest = options.body.length > 60 * 1024; // 留一些余量
    }
    
    const fetchOptions: RequestInit = {
      ...options,
      headers: {
        ...getAuthHeaders(),
        ...options.headers,
      },
      signal: controller.signal,
    };
    
    // keepalive 不能与大请求体一起使用
    // 包括：FormData、大的 JSON（含 base64）等
    if (!isFormData && !isLargeRequest) {
      fetchOptions.keepalive = true;
    }
    
    if (typeof window !== 'undefined') {
      if (isFormData) {
        console.info('【authFetch】发送 FormData 请求，body entries:', 
          Array.from((options.body as FormData).entries()).map(([k, v]) => 
            `${k}: ${v instanceof File ? `File(${v.name}, ${v.size} bytes)` : v}`
          )
        );
      } else if (isLargeRequest) {
        console.info('【authFetch】发送大 JSON 请求，大小:', 
          `${(options.body as string).length} bytes (${((options.body as string).length / 1024).toFixed(1)} KB)`,
          '，keepalive 已禁用'
        );
      }
    }
    
    const response = await fetch(fullUrl, fetchOptions);
    
    clearTimeout(timeoutId);
    const duration = Date.now() - startTime;
    
    if (isServerSide && logger) {
      logger.debug(`authFetch - 响应`, {
        url: fullUrl,
        status: response.status,
        duration: `${duration}ms`
      });
    } else if (typeof window !== 'undefined') {
      console.info('【authFetch】响应状态:', response.status);
    }
    
    // 自动处理 401 错误
    if (response.status === 401 && typeof window !== 'undefined') {
      // 清除本地认证信息
      localStorage.removeItem('auth');
      localStorage.removeItem('sessionId');
      
      // 获取当前页面路径作为回调URL
      const currentPath = window.location.pathname + window.location.search;
      const callbackUrl = encodeURIComponent(currentPath);
      
      // 跳转到登录页
      window.location.href = `${basePath}/auth/login?callbackUrl=${callbackUrl}`;
      
      // 返回一个永远不会 resolve 的 Promise，阻止后续代码执行
      return new Promise(() => {});
    }

    return response;
  } catch (error) {
    const isNetworkError = 
      error instanceof TypeError && 
      (error.message.includes('fetch failed') || 
       error.message.includes('Failed to fetch') ||
       error.message.includes('NetworkError') ||
       error.message.includes('ERR_NETWORK'));
    
    const isTimeoutError = 
      error instanceof Error && 
      (error.name === 'AbortError' || error.message.includes('aborted'));
    
    if (isServerSide && logger) {
      logger.error(`authFetch - 请求失败`, {
        url: fullUrl,
        error: error instanceof Error ? {
          message: error.message,
          name: error.name,
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          cause: (error as any).cause,
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          code: (error as any).code
        } : error,
        isNetworkError,
        isTimeoutError,
        retryCount
      });
    } else if (typeof window !== 'undefined') {
      console.error('【authFetch】请求失败:', error);
    }
    
    // 网络错误时重试
    if ((isNetworkError || isTimeoutError) && retryCount < maxRetries) {
      if (isServerSide && logger) {
        logger.info(`authFetch - 准备重试 ${retryCount + 1}/${maxRetries}，延迟 ${retryDelay}ms`);
      }
      
      // 等待后重试
      await new Promise(resolve => setTimeout(resolve, retryDelay * (retryCount + 1)));
      return authFetch(url, options, retryCount + 1);
    }
    
    throw error;
  }
}

/**
 * 检查用户是否已登录（仅检查本地存储）
 * 注意：这只是快速检查，不验证 token 是否真的有效
 * @returns boolean
 */
export function isAuthenticated(): boolean {
  if (typeof window === 'undefined') return false;
  
  const auth = localStorage.getItem('auth');
  if (!auth) return false;
  
  try {
    const { access } = JSON.parse(auth);
    return !!access;
  } catch {
    return false;
  }
}

/**
 * 验证 token 是否真的有效
 * @returns Promise<boolean> token 是否有效
 */
export async function verifyToken(): Promise<boolean> {
  if (!isAuthenticated()) return false;
  
  try {
    const auth = localStorage.getItem('auth');
    if (!auth) return false;
    
    const { access } = JSON.parse(auth);
    // 使用本地 API 代理
    const basePath = process.env.NEXT_PUBLIC_BASE_PATH || '';
    const response = await fetch(`${basePath}/api/auth/token/verify`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
      body: JSON.stringify({ token: access }),
      credentials: 'include', // 包含 cookies
    });
    
    if (response.ok) {
      return true;
    } else if (response.status === 401) {
      // Token 无效，清理本地存储
      localStorage.removeItem('auth');
      localStorage.removeItem('sessionId');
      return false;
    }
    
    return false;
  } catch {
    return false;
  }
}

/**
 * 清除认证信息并重定向到登录页
 */
export function logout(): void {
  if (typeof window === 'undefined') return;
  
  localStorage.removeItem('auth');
  const basePath = process.env.NEXT_PUBLIC_BASE_PATH || '';
  window.location.href = `${basePath}/auth/login`;
}