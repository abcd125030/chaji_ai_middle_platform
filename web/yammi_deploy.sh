#!/bin/bash

# Next.js Standalone 部署脚本 - Yammi本地版本

echo "🚀 开始部署 Next.js Standalone 应用 (Yammi本地环境)..."

# 确保在正确的目录
cd "$(dirname "$0")"

# 1. 构建应用
echo "📦 构建应用..."
pnpm build

# 2. 复制静态文件到 standalone 目录
echo "📋 复制静态文件..."
cp -r .next/static .next/standalone/.next/
cp -r public .next/standalone/

# 3. 重启 PM2 服务
echo "♻️ 重启 PM2 服务..."
pm2 reload ecosystem.yammi.config.cjs

# 4. 保存 PM2 配置
pm2 save

echo "✅ 部署完成！"
echo "📌 提示：确保服务器上的环境变量已正确配置"