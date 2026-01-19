#!/bin/bash

echo "========================================="
echo "Next.js Studio 部署诊断脚本"
echo "========================================="
echo ""

# 1. 检查 PM2 进程状态
echo "1. 检查 PM2 进程状态:"
echo "-------------------"
pm2 list | grep -E "frago-studio|3323"
echo ""

# 2. 检查端口监听
echo "2. 检查 3323 端口监听状态:"
echo "-------------------------"
netstat -tlnp | grep 3323 || lsof -i :3323
echo ""

# 3. 测试本地访问
echo "3. 测试本地访问:"
echo "---------------"
echo "测试根路径:"
curl -I http://127.0.0.1:3323/ 2>/dev/null | head -5
echo ""
echo "测试 _next 静态资源:"
curl -I http://127.0.0.1:3323/_next/static 2>/dev/null | head -5
echo ""

# 4. 检查 standalone 目录结构
echo "4. 检查 standalone 目录结构:"
echo "---------------------------"
cd /www/wwwroot/github/X/web
echo "检查 .next/standalone 目录:"
ls -la .next/standalone/ 2>/dev/null | head -10
echo ""
echo "检查静态文件是否已复制:"
echo "- .next/standalone/.next/static 存在: $([ -d .next/standalone/.next/static ] && echo '✓' || echo '✗')"
echo "- .next/standalone/public 存在: $([ -d .next/standalone/public ] && echo '✓' || echo '✗')"
echo ""

# 5. 检查 PM2 日志
echo "5. PM2 最近错误日志:"
echo "-------------------"
pm2 logs frago-studio --err --lines 10 --nostream 2>/dev/null || echo "无法获取日志"
echo ""

# 6. 修复建议
echo "========================================="
echo "如果发现问题，执行以下修复命令:"
echo "========================================="
echo ""
echo "# 1. 重新构建和复制静态文件:"
echo "cd /www/wwwroot/github/X/web"
echo "pnpm build"
echo "cp -r .next/static .next/standalone/.next/"
echo "cp -r public .next/standalone/"
echo ""
echo "# 2. 重启 PM2:"
echo "pm2 restart frago-studio"
echo ""
echo "# 3. 如果 PM2 进程不存在，启动它:"
echo "pm2 start ecosystem.sg.config.cjs"
echo ""
echo "# 4. 检查 Nginx 配置并重载:"
echo "nginx -t && nginx -s reload"