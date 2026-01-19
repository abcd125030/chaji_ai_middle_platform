import type { NextConfig } from "next";
import { PHASE_PRODUCTION_BUILD } from 'next/constants';
import createMDX from '@next/mdx';

const withMDX = createMDX({
  options: {
    remarkPlugins: [],
    rehypePlugins: [],
  },
});

export default (phase: string): NextConfig => {
  const isBuild = phase === PHASE_PRODUCTION_BUILD;
  const isProd = process.env.NODE_ENV === 'production';

  const config: NextConfig = {
    basePath: process.env.NEXT_PUBLIC_BASE_PATH || '',

    // 确保输出为 standalone 模式（生产环境推荐）
    output: 'standalone' as const,

    // 禁用 X-Powered-By 头（安全考虑）
    poweredByHeader: false,

    // 配置静态文件导出
    trailingSlash: false,

    // 允许的开发源（用于跨域资源访问）
    // 这解决了 Next.js 在代理后面运行时的跨域警告
    // 注意：只需要域名，不需要协议
    allowedDevOrigins: [
      'aigc.chagee.com',
      'aigc.bwcj.biz',
    ],
    
    // 配置外部图片 - 禁用优化以允许任何域名
    images: {
      unoptimized: true,
    },
    
    // 确保开发和生产环境的一致性
    generateEtags: false,
    
    // 支持 MDX 文件扩展名
    pageExtensions: ['js', 'jsx', 'ts', 'tsx', 'md', 'mdx'],
    
    /* config options here */
    compiler: {
      // 生产环境移除所有 console 输出，仅保留 error 用于错误追踪
      // 开发环境保留所有 console
      removeConsole: isProd ? {
        // 只保留 error 用于错误追踪
        // 移除 log、info、warn、debug、trace 提升安全性
        exclude: ['error'],
      } : false,
    },
  };

  return withMDX(config);
};
