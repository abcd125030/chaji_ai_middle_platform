module.exports = {
    apps: [
        // 飞书 WebSocket 长连接客户端 - 生产环境
        {
            name: "feishu_ws",
            namespace: "default",
            script: "/www/wwwroot/repos/X/backend/lark_oapi_main.py",

            // 进程配置
            exec_mode: "fork",
            interpreter: "/www/wwwroot/repos/X/backend/.venv/bin/python",

            // 日志配置
            error_file: "/www/wwwroot/repos/X/backend/logs/feishu/feishu-ws-err.log",
            out_file: "/www/wwwroot/repos/X/backend/logs/feishu/feishu-ws-out.log",
            log_file: "/www/wwwroot/repos/X/backend/logs/feishu/feishu-ws-combined.log",
            combine_logs: true,
            merge_logs: true,

            // 日志旋转配置（生产环境：保留30天）
            log_rotate_interval: "0 0 * * *",
            log_rotate_max_size: "100M",
            log_rotate_keep: 30,
            log_rotate_compress: true,

            // 监控和重启配置
            watch: false,
            max_restarts: 10,
            min_uptime: "30s",
            autorestart: true,
            restart_delay: 5000,
            exp_backoff_restart_delay: 100,

            // 时区设置
            timezone: "Asia/Shanghai",

            // 环境变量
            env: {
                NODE_ENV: "production",
                DJANGO_SETTINGS_MODULE: "backend.settings",
                PATH: process.env.PATH,
            },

            // PID 文件路径
            pid_file: "/www/wwwroot/repos/X/backend/logs/pids/feishu_ws.pid",

            // 内存限制
            max_memory_restart: "800M",

            // 工作目录（重要：确保能找到 .env 文件）
            cwd: "/www/wwwroot/repos/X/backend",

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
