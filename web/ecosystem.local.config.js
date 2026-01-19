const path = require('path');

// 动态路径配置 - 自动适配任何开发机
const BASE_DIR = __dirname;  // 配置文件所在目录，即 web/
const LOGS_DIR = path.join(BASE_DIR, 'logs');

module.exports = {
    apps: [
        // Next.js 开发服务器 - 本地开发环境
        {
            name: "ChageeX_Web_Local",
            namespace: "default",
            script: "pnpm",
            args: "dev",

            // 进程配置
            exec_mode: "fork",
            instances: 1,

            // 日志配置
            error_file: path.join(LOGS_DIR, 'pm2', 'pm2-nextjs-err.log'),
            out_file: path.join(LOGS_DIR, 'pm2', 'pm2-nextjs-out.log'),
            log_file: path.join(LOGS_DIR, 'pm2', 'pm2-nextjs-combined.log'),
            combine_logs: true,
            merge_logs: true,

            // 日志旋转配置（本地开发环境：保留近3天）
            log_rotate_interval: "0 0 * * *",
            log_rotate_max_size: "100M",
            log_rotate_keep: 3,
            log_rotate_compress: true,

            // 监控和重启配置
            // Next.js 自带热重载，无需 PM2 watch
            watch: false,
            autorestart: true,
            max_restarts: 10,
            min_uptime: "30s",
            restart_delay: 4000,
            exp_backoff_restart_delay: 100,

            // 环境变量
            env: {
                NODE_ENV: "development",
                PATH: process.env.PATH,
            },

            // PID 文件路径
            pid_file: path.join(LOGS_DIR, 'pids', 'nextjs_local.pid'),

            // 内存限制（前端开发服务器通常不需要太多内存）
            max_memory_restart: "512M",

            // 工作目录
            cwd: BASE_DIR,

            // 忽略监控的文件和目录（即使 watch 为 false 也建议配置）
            ignore_watch: [
                "node_modules",
                ".next",
                "out",
                "build",
                "dist",
                "logs",
                "*.log",
                ".git",
                "coverage",
                ".coverage",
                ".env*",
                "*.pid",
                "*.sock",
                ".DS_Store",
                "Thumbs.db",
                "public/uploads",
                "tmp",
                "temp",
                "cache",
            ],
        },
    ],
};
