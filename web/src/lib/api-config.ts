/**
 * API 配置工具
 * 根据运行环境智能选择 API URL
 */

/**
 * 获取 API 基础 URL
 * 服务端使用内网地址，客户端使用公网地址
 */
export function getApiBaseUrl(): string {
  // 服务端环境（Node.js）
  if (typeof window === 'undefined') {
    // 优先使用服务端专用配置
    if (process.env.SERVER_API_BASE_URL) {
      return process.env.SERVER_API_BASE_URL;
    }
  }
  
  // 客户端环境或没有服务端配置时，使用公网地址
  return process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:6066/api';
}

/**
 * 判断是否为服务端环境
 */
export function isServerSide(): boolean {
  return typeof window === 'undefined';
}

/**
 * 获取完整的 API URL
 * @param path API 路径（如 '/auth/profile/'）
 */
export function getApiUrl(path: string): string {
  const baseUrl = getApiBaseUrl();
  // 确保路径以 / 开头
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;
  return `${baseUrl}${normalizedPath}`;
}