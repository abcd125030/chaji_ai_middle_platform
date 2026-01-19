module.exports = {
    apps: [
        // Django 应用配置 - 生产环境（16核 123GB内存服务器）
        {
            name: "ChageeX_Test",
            namespace: "default",
            script: "/www/wwwroot/repos/X/backend/.venv/bin/gunicorn",
            args: "backend.wsgi:application --bind 0.0.0.0:6066 --workers 8 --timeout 300 --graceful-timeout 60 --keep-alive 5 --worker-class sync",

            // 进程配置
            exec_mode: "fork_mode",
            interpreter: "/www/wwwroot/repos/X/backend/.venv/bin/python",

            // 日志配置
            error_file: "/www/wwwroot/repos/X/backend/logs/pm2/pm2-django-err.log",
            out_file: "/www/wwwroot/repos/X/backend/logs/pm2/pm2-django-out.log",
            log_file: "/www/wwwroot/repos/X/backend/logs/pm2/pm2-django-combined.log",
            combine_logs: true,
            merge_logs: true,

            // 日志旋转配置
            log_rotate_interval: "0 0 * * *",
            log_rotate_max_size: "200M",
            log_rotate_keep: 3,
            log_rotate_compress: true,

            // 监控和重启配置
            watch: false,
            watch_delay: 1000,
            max_restarts: 10,
            min_uptime: "30s",
            autorestart: true,
            restart_delay: 4000,
            exp_backoff_restart_delay: 100,

            // 环境变量
            env: {
                NODE_ENV: "production",
                DJANGO_SETTINGS_MODULE: "backend.settings",
                PATH: process.env.PATH,
                IS_PRODUCTION_ENV: "true",
            },

            // PID 文件路径
            pid_file: "/www/wwwroot/repos/X/backend/logs/pids/backend_test.pid",

            // 内存限制（生产环境 4GB）
            max_memory_restart: "4G",

            // 工作目录
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
        // 资源配置：适合 16核 123GB 内存的生产服务器
        ...Array.from({ length: 6 }, (_, i) => ({
            // 增加到 6 个 workers（充分利用16核CPU）
            name: `celery_worker_${i + 1}`,
            script: "/www/wwwroot/repos/X/backend/.venv/bin/celery",
            args: `-A backend worker --pool=gevent --concurrency=100 --loglevel=info --max-memory-per-child=200000000 --max-tasks-per-child=500 --prefetch-multiplier=3 -n worker_${
                i + 1
            }@%(h)s --without-heartbeat --without-gossip --without-mingle -Q celery,image_normal_priority,image_high_priority,image_batch`,

            // PID 文件路径
            pid_file: `/www/wwwroot/repos/X/backend/logs/pids/celery_worker_${i + 1}.pid`,

            // 进程配置
            interpreter: "/www/wwwroot/repos/X/backend/.venv/bin/python",
            exec_mode: "fork",
            instances: 1,

            // 自动重启配置（生产环境更稳定）
            autorestart: true,
            max_restarts: 10,
            min_uptime: "30s",
            restart_delay: 4000,
            exp_backoff_restart_delay: 100,

            // 内存限制（18GB - 6个worker，每个18GB，总计108GB，留15GB给系统）
            max_memory_restart: "18G",

            // 日志配置（与local保持一致的目录结构）
            error_file: `/www/wwwroot/repos/X/backend/logs/celery/pm2_celery_worker_${
                i + 1
            }_error.log`,
            out_file: `/www/wwwroot/repos/X/backend/logs/celery/pm2_celery_worker_${
                i + 1
            }_out.log`,
            log_file: `/www/wwwroot/repos/X/backend/logs/celery/pm2_celery_worker_${
                i + 1
            }_combined.log`,
            combine_logs: true,
            merge_logs: true,

            // 日志轮转（生产环境保留更多日志）
            log_rotate_interval: "0 0 * * *",
            log_rotate_max_size: "200M",
            log_rotate_keep: 3,
            log_rotate_compress: true,

            // 环境变量
            env: {
                C_FORCE_ROOT: "1",
                OBJC_DISABLE_INITIALIZE_FORK_SAFETY: "YES",
                GEVENT_SUPPORT: "true",
                DJANGO_SETTINGS_MODULE: "backend.settings",
                PATH: process.env.PATH,
                // 生产环境特定变量
                CELERY_WORKER_CONCURRENCY: "100",
                CELERY_NUM_WORKERS: "6",
                CELERY_PREFETCH_MULTIPLIER: "3",
                CELERY_MAX_MEMORY_PER_CHILD: "200000000",
                IS_PRODUCTION_ENV: "true",
            },

            // 监控配置
            instance_var: "INSTANCE_ID",
            kill_timeout: 10000,
            listen_timeout: 10000,

            // 工作目录
            cwd: "/www/wwwroot/repos/X/backend",
        })),

        // Celery PDF Extractor Workers - 专门处理 PDF 提取任务
        // 测试环境：2个worker，每个15并发（适配16核CPU，123GB内存）
        ...Array.from({ length: 2 }, (_, i) => ({
            name: `celery_pdf_extractor_${i + 1}`,
            script: "/www/wwwroot/repos/X/backend/.venv/bin/celery",
            args: `-A backend.celery_pdf_extractor worker --pool=gevent --concurrency=15 --loglevel=info -n pdf_extractor_${i + 1}@%(h)s --pidfile=/www/wwwroot/repos/X/backend/logs/pids/celery_pdf_extractor_${i + 1}.pid`,

            // 进程配置
            interpreter: "/www/wwwroot/repos/X/backend/.venv/bin/python",
            exec_mode: "fork",
            instances: 1,

            // 自动重启配置
            autorestart: true,
            max_restarts: 10,
            min_uptime: "30s",
            restart_delay: 4000,
            exp_backoff_restart_delay: 100,

            // 内存限制（PDF 任务需要更多内存）
            max_memory_restart: "10G",

            // 日志配置
            error_file: `/www/wwwroot/repos/X/backend/logs/celery/pm2_celery_pdf_extractor_${i + 1}_error.log`,
            out_file: `/www/wwwroot/repos/X/backend/logs/celery/pm2_celery_pdf_extractor_${i + 1}_out.log`,
            log_file: `/www/wwwroot/repos/X/backend/logs/celery/pm2_celery_pdf_extractor_${i + 1}_combined.log`,
            combine_logs: true,
            merge_logs: true,

            // 日志轮转
            log_rotate_interval: "0 0 * * *",
            log_rotate_max_size: "200M",
            log_rotate_keep: 3,
            log_rotate_compress: true,

            // 环境变量
            env: {
                C_FORCE_ROOT: "1",
                OBJC_DISABLE_INITIALIZE_FORK_SAFETY: "YES",
                GEVENT_SUPPORT: "true",
                DJANGO_SETTINGS_MODULE: "backend.settings",
                PATH: process.env.PATH,
                IS_PRODUCTION_ENV: "true",
            },

            // 监控配置
            kill_timeout: 10000,
            listen_timeout: 10000,

            // 工作目录
            cwd: "/www/wwwroot/repos/X/backend",
        })),

        // Celery Beat 配置（生产环境）
        {
            name: "celery_beat",
            script: "/www/wwwroot/repos/X/backend/.venv/bin/celery",
            args: "-A backend beat --loglevel=warning",

            // PID 文件路径
            pid_file: "/www/wwwroot/repos/X/backend/logs/pids/celerybeat.pid",

            interpreter: "/www/wwwroot/repos/X/backend/.venv/bin/python",
            exec_mode: "fork",
            instances: 1,

            autorestart: true,
            max_restarts: 5,
            min_uptime: "60s",

            error_file:
                "/www/wwwroot/repos/X/backend/logs/celery/pm2_celery_beat_error.log",
            out_file:
                "/www/wwwroot/repos/X/backend/logs/celery/pm2_celery_beat_out.log",
            log_file:
                "/www/wwwroot/repos/X/backend/logs/celery/pm2_celery_beat_combined.log",
            combine_logs: true,
            merge_logs: true,

            // 日志轮转
            log_rotate_interval: "0 0 * * *",
            log_rotate_max_size: "200M",
            log_rotate_keep: 3,
            log_rotate_compress: true,

            env: {
                C_FORCE_ROOT: "1",
                DJANGO_SETTINGS_MODULE: "backend.settings",
                IS_PRODUCTION_ENV: "true",
            },

            cwd: "/www/wwwroot/repos/X/backend",
        },
    ],
};