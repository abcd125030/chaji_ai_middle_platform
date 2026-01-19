/**
 * 菜单访问控制工具
 * 根据环境变量配置检查路由是否可访问
 */

interface RouteConfig {
  path: string;
  menuKey: string;
  envVar: string;
}

// TopBar 路由配置
const TOPBAR_ROUTES: RouteConfig[] = [
  { path: '/chat', menuKey: 'agentic', envVar: 'NEXT_PUBLIC_TOPBAR_MENU_SHOW' },
  { path: '/presentation', menuKey: 'presentation', envVar: 'NEXT_PUBLIC_TOPBAR_MENU_SHOW' },
  { path: '/tools', menuKey: 'tools', envVar: 'NEXT_PUBLIC_TOPBAR_MENU_SHOW' },
  { path: '/docs', menuKey: 'docs', envVar: 'NEXT_PUBLIC_TOPBAR_MENU_SHOW' },
  { path: '/dashboard', menuKey: 'dashboard', envVar: 'NEXT_PUBLIC_TOPBAR_MENU_SHOW' }
];

// ChatTopBar 路由配置
const CHAT_ROUTES: RouteConfig[] = [
  { path: '/history', menuKey: 'history', envVar: 'NEXT_PUBLIC_CHAT_MENU_SHOW' },
  { path: '/subscription', menuKey: 'payments', envVar: 'NEXT_PUBLIC_CHAT_MENU_SHOW' }
  // Create 不需要检查，因为它指向 /chat，已在 TOPBAR_ROUTES 中
];

/**
 * 检查路由是否允许访问
 * @param pathname 当前路径
 * @returns true 表示允许访问，false 表示拒绝访问
 */
export function isRouteAccessible(pathname: string): boolean {
  // 移除查询参数和片段
  let cleanPath = pathname.split('?')[0].split('#')[0];
  
  // 移除 base path（如果存在）
  const basePath = process.env.NEXT_PUBLIC_BASE_PATH || '';
  if (basePath && cleanPath.startsWith(basePath)) {
    cleanPath = cleanPath.slice(basePath.length) || '/';
  }
  
  // 检查是否是受保护的路由
  const allRoutes = [...TOPBAR_ROUTES, ...CHAT_ROUTES];
  const routeConfig = allRoutes.find(route => 
    cleanPath === route.path || cleanPath.startsWith(route.path + '/')
  );
  
  if (!routeConfig) {
    // 不在保护列表中的路由，默认允许访问
    return true;
  }
  
  // 检查菜单项是否在显示列表中
  // 注意：在客户端代码中需要直接访问环境变量，不能使用动态键
  let menuShow: string | undefined;
  if (routeConfig.envVar === 'NEXT_PUBLIC_TOPBAR_MENU_SHOW') {
    menuShow = process.env.NEXT_PUBLIC_TOPBAR_MENU_SHOW;
  } else if (routeConfig.envVar === 'NEXT_PUBLIC_CHAT_MENU_SHOW') {
    menuShow = process.env.NEXT_PUBLIC_CHAT_MENU_SHOW;
  }
  
  if (!menuShow || menuShow.trim() === '') {
    // 环境变量为空，表示隐藏所有菜单项，路由不可访问
    return false;
  }
  
  const showItems = menuShow.split(',').map(s => s.trim());
  return showItems.includes(routeConfig.menuKey);
}

/**
 * 获取可访问的路由列表
 * @returns 允许访问的路由数组
 */
export function getAccessibleRoutes(): string[] {
  const allRoutes = [...TOPBAR_ROUTES, ...CHAT_ROUTES];
  return allRoutes
    .filter(route => isRouteAccessible(route.path))
    .map(route => route.path);
}

/**
 * 获取第一个可访问的路由（保留但不再用于强制重定向）
 * @returns 第一个可访问的路由，如果没有则返回首页
 */
export function getFirstAccessibleRoute(): string {
  const accessibleRoutes = getAccessibleRoutes();
  return accessibleRoutes.length > 0 ? accessibleRoutes[0] : '/';
}