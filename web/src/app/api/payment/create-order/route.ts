/**
 * 支付订单创建专用API路由
 * 自动注入安全的URL配置，避免前端暴露敏感信息
 */

import { NextRequest, NextResponse } from 'next/server';
import { proxyToBackend } from '@/lib/backend-proxy';
import { logger } from '@/lib/server-logger';

export async function POST(request: NextRequest) {
  try {
    // 解析前端请求
    const body = await request.json();
    
    // 从环境变量获取URL配置
    // 支付回调域名 - 仅用于第三方支付平台的后端回调
    const paymentCallbackUrl = process.env.PAYMENT_CALLBACK_BASE_URL || 
                               'https://payment-domain.com';
    // 用户可见域名 - 用于用户页面跳转
    const userFacingUrl = process.env.USER_FACING_BASE_URL || 
                         process.env.NEXT_PUBLIC_BASE_URL ||
                         'http://localhost:3000';
    const basePath = process.env.NEXT_PUBLIC_BASE_PATH || '';
    
    // 构建安全的URL配置
    const enhancedBody = {
      ...body,
      // frontend_url 使用用户可见域名（用于构建跳转链接）
      frontend_url: `${userFacingUrl}${basePath}`,
      // 支付成功后跳转页面 - 使用用户域名
      return_url: `${userFacingUrl}${basePath}/subscription/success`,
      // 支付失败后跳转页面 - 使用用户域名
      callback_url: `${userFacingUrl}${basePath}/subscription/fail`,
      // 传递支付回调域名给后端，后端会用它构建notify_url
      // notify_url必须是在支付平台登记的域名
      payment_callback_base: paymentCallbackUrl
    };
    
    // 创建新的请求，注入增强后的body
    const enhancedRequest = new NextRequest(request.url, {
      method: 'POST',
      headers: request.headers,
      body: JSON.stringify(enhancedBody)
    });
    
    // 代理到后端
    return proxyToBackend(enhancedRequest, '/payment/orders/create_order/');
    
  } catch (error) {
    logger.error('创建支付订单失败:', error);
    return NextResponse.json(
      { 
        status: 'error', 
        error: '创建订单失败',
        message: error instanceof Error ? error.message : '未知错误'
      },
      { status: 500 }
    );
  }
}