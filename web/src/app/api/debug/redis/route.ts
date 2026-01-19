/**
 * Redis SSE 调试端点
 */

import { NextRequest, NextResponse } from 'next/server';
import Redis from 'ioredis';

export async function GET(_request: NextRequest) {
  const config = {
    host: process.env.REDIS_HOST || 'localhost',
    port: parseInt(process.env.REDIS_PORT || '6379'),
    password: process.env.REDIS_PASSWORD,
    db: parseInt(process.env.REDIS_SSE_DB || '3'),
    configured: !!(process.env.REDIS_HOST || process.env.REDIS_PORT)
  };

  let connectionStatus = 'unknown';
  let testResult = null;
  
  if (config.configured) {
    try {
      const client = new Redis({
        host: config.host,
        port: config.port,
        password: config.password,
        db: config.db,
        connectTimeout: 3000
      });
      
      // 测试连接
      await client.ping();
      connectionStatus = 'connected';
      
      // 测试发布订阅
      const testChannel = 'sse:test';
      const testMessage = { type: 'test', timestamp: new Date().toISOString() };
      
      await client.publish(testChannel, JSON.stringify(testMessage));
      testResult = 'publish successful';
      
      client.disconnect();
    } catch (error) {
      connectionStatus = 'failed';
      testResult = error instanceof Error ? error.message : 'Unknown error';
    }
  } else {
    connectionStatus = 'not configured';
  }

  return NextResponse.json({
    redis: {
      config,
      connectionStatus,
      testResult
    },
    environment: {
      NODE_ENV: process.env.NODE_ENV,
      PM2_INSTANCE_ID: process.env.PM2_INSTANCE_ID,
      pm2_instance_var: process.env.pm2_instance_var,
      isClusterMode: !!(process.env.PM2_INSTANCE_ID || process.env.pm2_instance_var)
    },
    timestamp: new Date().toISOString()
  });
}