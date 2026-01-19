#!/usr/bin/env node

/**
 * 测试 Redis SSE 功能
 */

const Redis = require('ioredis');

// 模拟环境变量
const REDIS_CONFIG = {
  host: process.env.REDIS_HOST || 'localhost',
  port: parseInt(process.env.REDIS_PORT || '6379'),
  password: process.env.REDIS_PASSWORD,
  db: parseInt(process.env.REDIS_SSE_DB || '3'),
};

console.log('Redis 配置:', REDIS_CONFIG);

// 创建发布者
const publisher = new Redis(REDIS_CONFIG);

// 创建订阅者
const subscriber = new Redis(REDIS_CONFIG);

const sessionId = 'test-session-123';
const channel = `sse:${sessionId}`;

// 订阅消息
subscriber.subscribe(channel, (err) => {
  if (err) {
    console.error('订阅失败:', err);
    process.exit(1);
  }
  console.log(`订阅成功: ${channel}`);
});

subscriber.on('message', (receivedChannel, message) => {
  console.log(`收到消息 [${receivedChannel}]:`, message);
  try {
    const data = JSON.parse(message);
    console.log('解析后的数据:', data);
  } catch (e) {
    console.error('解析失败:', e);
  }
});

// 模拟发送消息
setTimeout(() => {
  console.log('\n发送测试消息...');
  
  // 模拟进度消息
  const messages = [
    { type: 'plan', data: { step: 'Planning...', progress: 10 } },
    { type: 'tool_output', data: { tool: 'Chat', status: 'running', progress: 30 } },
    { type: 'reflection', data: { content: 'Analyzing...', progress: 60 } },
    { type: 'final_message', data: { answer: '你好！', progress: 100 } }
  ];
  
  let index = 0;
  const interval = setInterval(() => {
    if (index >= messages.length) {
      clearInterval(interval);
      setTimeout(() => {
        console.log('\n测试完成，关闭连接...');
        publisher.disconnect();
        subscriber.disconnect();
        process.exit(0);
      }, 1000);
      return;
    }
    
    const msg = messages[index++];
    console.log(`发送: ${msg.type}`);
    publisher.publish(channel, JSON.stringify(msg));
  }, 1000);
}, 1000);

// 错误处理
publisher.on('error', (err) => console.error('Publisher error:', err));
subscriber.on('error', (err) => console.error('Subscriber error:', err));