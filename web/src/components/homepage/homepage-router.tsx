'use client';

import React from 'react';
import { siteConfig, HomepageType } from '@/lib/site-config';
import dynamic from 'next/dynamic';

// 动态导入首页组件，支持代码分割
const EnterpriseHomepage = dynamic(() => import('./enterprise-homepage'), {
  loading: () => <div className="flex items-center justify-center min-h-screen">加载中...</div>,
});

const PublicHomepage = dynamic(() => import('./public-homepage'), {
  loading: () => <div className="flex items-center justify-center min-h-screen">加载中...</div>,
});

// 首页组件映射表
const homepageComponents = {
  [HomepageType.ENTERPRISE]: EnterpriseHomepage,
  [HomepageType.PUBLIC]: PublicHomepage,
} as const;

/**
 * 首页路由选择器
 * 根据配置动态选择并渲染对应的首页组件
 */
export default function HomepageRouter() {
  const homepageType = siteConfig.homepageType;
  
  // 获取对应的首页组件
  const HomepageComponent = homepageComponents[homepageType] || homepageComponents[HomepageType.ENTERPRISE];
  
  // 错误边界处理
  if (!HomepageComponent) {
    console.error(`Invalid homepage type: ${homepageType}`);
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <h1 className="text-2xl font-bold text-red-600 mb-4">配置错误</h1>
          <p className="text-gray-600">无效的首页类型配置：{homepageType}</p>
        </div>
      </div>
    );
  }
  
  return <HomepageComponent />;
}