/**
 * 站点配置
 * 从环境变量读取站点名称相关配置，支持部署时自定义
 */

// 首页类型枚举
export enum HomepageType {
  ENTERPRISE = 'enterprise',
  PUBLIC = 'public',
}

// 首页配置映射
export const homepageConfig = {
  [HomepageType.ENTERPRISE]: {
    title: '霸王茶姬 AI 实验室',
    description: '企业内部智能化平台',
    theme: 'enterprise',
  },
  [HomepageType.PUBLIC]: {
    title: 'AI Studio',
    description: '智能化、模块化、可扩展的AI工具平台',
    theme: 'public',
  },
} as const;

export const siteConfig = {
  // 站点简称，用于顶部导航栏等紧凑位置
  name: process.env.NEXT_PUBLIC_SITE_NAME || 'CHAGEE AI Studio',
  
  // 站点全称，用于登录页、法律文档等正式场合
  fullName: process.env.NEXT_PUBLIC_SITE_FULL_NAME || 'CHAGEE X AI 实验室平台',
  
  // AI助手名称，用于聊天界面
  assistantName: process.env.NEXT_PUBLIC_ASSISTANT_NAME || 'CHAGEE',
  
  // 浏览器标签页标题
  browserTitle: process.env.NEXT_PUBLIC_BROWSER_TITLE || 'CHAGEE X',
  
  // IndexedDB 数据库名称
  dbName: `${(process.env.NEXT_PUBLIC_SITE_NAME || 'chagee').toLowerCase().replace(/\s+/g, '-')}-ai-files`,
  
  // 营销页面标题
  marketingTitle: `${process.env.NEXT_PUBLIC_SITE_NAME || 'CHAGEE'} Marketing`,
  
  // 首页类型配置
  homepageType: (process.env.NEXT_PUBLIC_HOMEPAGE_TYPE as HomepageType) || HomepageType.ENTERPRISE,
  
  // 获取当前首页配置
  getCurrentHomepageConfig: () => {
    const type = siteConfig.homepageType;
    return homepageConfig[type] || homepageConfig[HomepageType.ENTERPRISE];
  },
};