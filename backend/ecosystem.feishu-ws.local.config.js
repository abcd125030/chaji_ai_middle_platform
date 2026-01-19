const path = require('path');

// 动态路径配置 - 自动适配任何开发机
const BASE_DIR = __dirname;  // 配置文件所在目录，即 backend/
const VENV_BIN = path.join(BASE_DIR, '.venv', 'bin');
const LOGS_DIR = path.join(BASE_DIR, 'logs');

module.exports = {
    apps: [
        // 飞书 WebSocket 长连接客户端 - 本地开发环境
        {
            name: "feishu_ws",
            namespace: "default",
            script: path.join(BASE_DIR, 'lark_oapi_main.py'),

            // 进程配置
            exec_mode: "fork",
            interpreter: path.join(VENV_BIN, 'python'),

            // 日志配置
            error_file: path.join(LOGS_DIR, 'feishu', 'feishu-ws-err.log'),
            out_file: path.join(LOGS_DIR, 'feishu', 'feishu-ws-out.log'),
            log_file: path.join(LOGS_DIR, 'feishu', 'feishu-ws-combined.log'),
            combine_logs: true,
            merge_logs: true,

            // 日志旋转配置（本地开发环境：保留近3天）
            log_rotate_interval: "0 0 * * *",
            log_rotate_max_size: "50M",
            log_rotate_keep: 3,
            log_rotate_compress: true,

            // 监控和重启配置
            watch: false,
            max_restarts: 10,
            min_uptime: "10s",
            autorestart: true,
            restart_delay: 3000,
            exp_backoff_restart_delay: 100,

            // 环境变量
            env: {
                NODE_ENV: "development",
                DJANGO_SETTINGS_MODULE: "backend.settings",
                PATH: process.env.PATH,
                // 禁用代理 - 飞书 WebSocket 需要直连，代理会导致 SSL 握手失败
                HTTP_PROXY: "",
                HTTPS_PROXY: "",
                http_proxy: "",
                https_proxy: "",
                NO_PROXY: "*",
            },

            // PID 文件路径
            pid_file: path.join(LOGS_DIR, 'pids', 'feishu_ws.pid'),

            // 内存限制（Django 初始化会占用较多内存）
            max_memory_restart: "800M",

            // 工作目录（重要：确保能找到 .env 文件）
            cwd: BASE_DIR,

            // 忽略监控的文件和目录
            ignore_watch: [
                "node_modules",
                "logs",
                "*.log",
                ".git",
                "**/*.pyc",
                "__pycache__",
                ".venv",
                "media",
                "static",
                "staticfiles",
            ],
        },
    ],
};
