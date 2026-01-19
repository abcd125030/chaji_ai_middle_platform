/**
 * 响应拦截器类
 * 用于统一处理 HTTP 响应，特别是认证错误
 */
export class ResponseInterceptor {
  private static isRedirecting = false;

  /**
   * 处理响应
   * @param response 原始响应对象
   * @returns 处理后的响应对象
   */
  static async handleResponse(response: Response): Promise<Response> {
    // 检查是否是认证错误
    if (response.status === 401 || response.status === 403) {
      // 只在客户端处理认证错误
      if (typeof window !== 'undefined' && !this.isRedirecting) {
        this.isRedirecting = true;
        await this.handleAuthError(response.status);
      }
      // 仍然返回原始响应，让调用方可以处理
      return response;
    }

    // 其他响应直接返回
    return response;
  }

  /**
   * 处理认证错误
   * @param status HTTP 状态码
   */
  private static async handleAuthError(status: number): Promise<void> {
    // 只在客户端环境执行
    if (typeof window === 'undefined') {
      return;
    }

    // 动态导入 toast，避免在服务端执行
    const { toast } = await import('react-hot-toast');

    // 清除本地存储的认证信息
    localStorage.removeItem('auth');
    localStorage.removeItem('sessionId');

    // 显示友好的错误提示
    const message = status === 401 
      ? '登录已过期，请重新登录' 
      : '您没有权限访问此资源';
    
    toast.error(message, {
      duration: 4000,
      id: 'auth-error', // 使用固定 ID 避免重复提示
    });

    // 延迟 2 秒后跳转到登录页
    setTimeout(() => {
      const basePath = process.env.NEXT_PUBLIC_BASE_PATH || '';
      window.location.href = `${basePath}/auth/login`;
    }, 2000);
  }

  /**
   * 重置重定向标志
   * 用于在成功登录后重置状态
   */
  static resetRedirectFlag(): void {
    this.isRedirecting = false;
  }
}