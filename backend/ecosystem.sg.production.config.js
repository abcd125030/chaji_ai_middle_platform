module.exports = {
    apps: [
        // Django 应用配置 - 生产环境
        {
            name: "ChageeX",
            namespace: "default",
            script: "/www/wwwroot/github/X/backend/.venv/bin/gunicorn",
            args: "backend.wsgi:application --bind 0.0.0.0:6066 --workers 8 --timeout 300 --graceful-timeout 60 --keep-alive 5 --worker-class sync",  // 优化：从20个workers降至8个（4核*2）

            // 进程配置
            exec_mode: "fork_mode",
            interpreter: "/www/wwwroot/github/X/backend/.venv/bin/python",

            // 日志配置（统一路径结构）
            error_file: "/www/wwwroot/github/X/backend/logs/pm2/pm2-django-err.log",
            out_file: "/www/wwwroot/github/X/backend/logs/pm2/pm2-django-out.log",
            log_file: "/www/wwwroot/github/X/backend/logs/pm2/pm2-django-combined.log",
            combine_logs: true,
            merge_logs: true,

            // 日志旋转配置
            log_rotate_interval: "0 0 * * *",
            log_rotate_max_size: "200M",
            log_rotate_keep: 10,
            log_rotate_compress: true,

            // 监控和重启配置
            watch: false,
            max_restarts: 10,
            min_uptime: "60s",
            autorestart: true,
            restart_delay: 4000,
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
            pid_file: "/www/wwwroot/github/X/backend/logs/pids/backend.pid",

            // 内存限制
            max_memory_restart: "2G",

            // 工作目录
            cwd: "/www/wwwroot/github/X/backend",

            // 忽略监控的文件和目录
            ignore_watch: [
                "node_modules",
                "logs",
                "*.log",
                ".git",
                "**/*.pyc",
                "__pycache__",
                ".venv",
                "celery_logs",
                "celery_pids",
                "media",
                "static",
                "staticfiles",
                "*.sqlite3",
                "db.sqlite3",
                "*.pid",
                "*.sock",
                "migrations",
                "*.env",
                ".env*",
                "coverage",
                ".coverage",
                "htmlcov",
                "*.egg-info",
                "build",
                "dist",
                ".pytest_cache",
                ".tox",
                "*.mo",
                "locale/*/LC_MESSAGES/*.mo",
                "tmp",
                "temp",
                "cache",
                ".DS_Store",
                "Thumbs.db",
            ],
        },

        // Celery Workers 配置 - 生产环境
        // 优化配置：2个worker，每个50并发，适配4核CPU
        ...Array.from({ length: 2 }, (_, i) => ({
            name: `celery_worker_${i + 1}`,
            script: "/www/wwwroot/github/X/backend/.venv/bin/celery",
            args: `-A backend worker --pool=gevent --concurrency=50 --loglevel=info --max-memory-per-child=800000 --max-tasks-per-child=1000 --prefetch-multiplier=2 -n gevent_worker_${
                i + 1
            }@%(h)s --without-heartbeat --without-gossip --without-mingle -Q celery,image_normal_priority,image_high_priority,image_batch`,

            // PID 文件路径
            pid_file: `/www/wwwroot/github/X/backend/logs/pids/celery_worker_${i + 1}.pid`,

            // 进程配置
            interpreter: "/www/wwwroot/github/X/backend/.venv/bin/python",
            exec_mode: "fork",
            instances: 1,

            // 自动重启配置
            autorestart: true,
            max_restarts: 10,
            min_uptime: "30s",
            restart_delay: 4000,
            exp_backoff_restart_delay: 100,

            // 内存限制（800MB per worker - 优化后配置）
            max_memory_restart: "800M",

            // 日志配置（统一路径结构）
            error_file: `/www/wwwroot/github/X/backend/logs/celery/pm2_celery_worker_${
                i + 1
            }_error.log`,
            out_file: `/www/wwwroot/github/X/backend/logs/celery/pm2_celery_worker_${
                i + 1
            }_out.log`,
            log_file: `/www/wwwroot/github/X/backend/logs/celery/pm2_celery_worker_${
                i + 1
            }_combined.log`,
            combine_logs: true,
            merge_logs: true,

            // 日志轮转
            log_rotate_interval: "0 0 * * *",
            log_rotate_max_size: "100M",
            log_rotate_keep: 7,
            log_rotate_compress: true,

            // 环境变量
            env: {
                C_FORCE_ROOT: "1",
                OBJC_DISABLE_INITIALIZE_FORK_SAFETY: "YES",
                GEVENT_SUPPORT: "true",
                DJANGO_SETTINGS_MODULE: "backend.settings",
                PATH: process.env.PATH,
            },

            // 监控配置
            instance_var: "INSTANCE_ID",
            kill_timeout: 10000,
            listen_timeout: 10000,

            // 工作目录
            cwd: "/www/wwwroot/github/X/backend",
        })),

        // Celery PDF Extractor Worker - 专门处理 PDF 提取任务
        // SG环境：1个worker，5并发（适配4核CPU）
        {
            name: "celery_pdf_extractor",
            script: "/www/wwwroot/github/X/backend/.venv/bin/celery",
            args: "-A backend.celery_pdf_extractor worker --pool=gevent --concurrency=5 --loglevel=info -n pdf_extractor@%(h)s --pidfile=/www/wwwroot/github/X/backend/logs/pids/celery_pdf_extractor.pid",

            // 进程配置
            interpreter: "/www/wwwroot/github/X/backend/.venv/bin/python",
            exec_mode: "fork",
            instances: 1,

            // 自动重启配置
            autorestart: true,
            max_restarts: 10,
            min_uptime: "30s",
            restart_delay: 4000,
            exp_backoff_restart_delay: 100,

            // 内存限制（PDF 任务需要更多内存）
            max_memory_restart: "1500M",

            // 日志配置
            error_file: "/www/wwwroot/github/X/backend/logs/celery/pm2_celery_pdf_extractor_error.log",
            out_file: "/www/wwwroot/github/X/backend/logs/celery/pm2_celery_pdf_extractor_out.log",
            log_file: "/www/wwwroot/github/X/backend/logs/celery/pm2_celery_pdf_extractor_combined.log",
            combine_logs: true,
            merge_logs: true,

            // 日志轮转
            log_rotate_interval: "0 0 * * *",
            log_rotate_max_size: "100M",
            log_rotate_keep: 7,
            log_rotate_compress: true,

            // 环境变量
            env: {
                C_FORCE_ROOT: "1",
                OBJC_DISABLE_INITIALIZE_FORK_SAFETY: "YES",
                GEVENT_SUPPORT: "true",
                DJANGO_SETTINGS_MODULE: "backend.settings",
                PATH: process.env.PATH,
            },

            // 监控配置
            kill_timeout: 10000,
            listen_timeout: 10000,

            // 工作目录
            cwd: "/www/wwwroot/github/X/backend",
        },

        // Celery Beat 配置
        {
            name: "celery_beat",
            script: "/www/wwwroot/github/X/backend/.venv/bin/celery",
            args: "-A backend beat --loglevel=warning",

            // PID 文件路径
            pid_file: "/www/wwwroot/github/X/backend/logs/pids/celerybeat.pid",

            interpreter: "/www/wwwroot/github/X/backend/.venv/bin/python",
            exec_mode: "fork",
            instances: 1,

            autorestart: true,
            max_restarts: 5,
            min_uptime: "60s",

            error_file:
                "/www/wwwroot/github/X/backend/logs/celery/pm2_celery_beat_error.log",
            out_file:
                "/www/wwwroot/github/X/backend/logs/celery/pm2_celery_beat_out.log",
            log_file:
                "/www/wwwroot/github/X/backend/logs/celery/pm2_celery_beat_combined.log",
            combine_logs: true,
            merge_logs: true,

            // 日志轮转
            log_rotate_interval: "0 0 * * *",
            log_rotate_max_size: "100M",
            log_rotate_keep: 7,
            log_rotate_compress: true,

            env: {
                C_FORCE_ROOT: "1",
                DJANGO_SETTINGS_MODULE: "backend.settings",
            },

            cwd: "/www/wwwroot/github/X/backend",
        },
    ],
};