/**
 * API 路由配置
 * 统一管理前端使用的 API 路径
 */

/**
 * 获取 API 路径
 * 根据配置决定是使用本地代理还是直接调用后端
 */
export function getApiRoute(path: string): string {
  const basePath = process.env.NEXT_PUBLIC_BASE_PATH || '';
  
  // 认证相关的路由使用本地代理
  if (path.startsWith('/auth/')) {
    return `${basePath}/api${path}`;
  }
  
  // 其他 API 可以通过 /api/backend 代理
  // 或者根据需要逐步迁移到专门的本地代理
  return `${basePath}/api/backend${path}`;
}

/**
 * API 路由映射
 * 定义各个功能模块的 API 路径
 */
export const API_ROUTES = {
  // 认证相关
  auth: {
    feishuLogin: '/auth/feishu/login',
    feishuCallback: '/auth/feishu/callback',
    tokenVerify: '/auth/token/verify',
    syncProfile: '/auth/sync-profile',
    profile: '/auth/profile',
  },
  
  // Chat Sessions
  chatSessions: {
    create: '/chat_sessions/create_or_get_session/',
    list: '/chat_sessions/get_sessions/',
    messages: '/chat_sessions/get_qas_by_session/',
  },
  
  // Pagtive
  pagtive: {
    projects: '/webapps/pagtive/projects/',
    generate: '/webapps/pagtive/generate/',
  },
  
  // 其他模块...
} as const;

/**
 * 构建完整的 API URL
 * @param route - API_ROUTES 中定义的路由
 * @returns 完整的 API URL
 */
export function buildApiUrl(route: string): string {
  return getApiRoute(route);
}