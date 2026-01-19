const path = require('path');

// 动态路径配置 - 自动适配任何开发机
const BASE_DIR = __dirname;  // 配置文件所在目录，即 backend/
const VENV_BIN = path.join(BASE_DIR, '.venv', 'bin');
const LOGS_DIR = path.join(BASE_DIR, 'logs');

module.exports = {
    apps: [
        // Django 应用配置 - 本地开发环境
        {
            name: "ChageeX_Local",
            namespace: "default",
            script: path.join(VENV_BIN, 'gunicorn'),
            args: "backend.wsgi:application --bind 0.0.0.0:6066 --workers 2 --timeout 300 --graceful-timeout 60 --keep-alive 5 --worker-class sync --reload",

            // 进程配置
            exec_mode: "fork_mode",
            interpreter: path.join(VENV_BIN, 'python'),

            // 日志配置
            error_file: path.join(LOGS_DIR, 'pm2', 'pm2-django-err.log'),
            out_file: path.join(LOGS_DIR, 'pm2', 'pm2-django-out.log'),
            log_file: path.join(LOGS_DIR, 'pm2', 'pm2-django-combined.log'),
            combine_logs: true,
            merge_logs: true,

            // 日志旋转配置（本地开发环境：保留近3天）
            log_rotate_interval: "0 0 * * *",
            log_rotate_max_size: "100M",
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
                NODE_ENV: "development",
                DJANGO_SETTINGS_MODULE: "backend.settings",
                PATH: process.env.PATH,
            },

            // PID 文件路径
            pid_file: path.join(LOGS_DIR, 'pids', 'backend_local.pid'),

            // 内存限制（本地环境降低到 1GB）
            max_memory_restart: "1G",

            // 工作目录
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

        // Celery Workers 配置 - 本地开发环境（处理图像等较重任务）
        ...Array.from({ length: 1 }, (_, i) => ({
            name: `celery_worker_${i + 1}`,
            script: path.join(VENV_BIN, 'celery'),
            args: `-A backend worker --pool=gevent --concurrency=2 --loglevel=info --max-memory-per-child=200000 --max-tasks-per-child=200 --prefetch-multiplier=1 -n gevent_worker_${
            i + 1
            }@%(h)s --without-heartbeat --without-gossip --without-mingle -Q celery,image_normal_priority,image_high_priority,image_batch --pidfile=${path.join(LOGS_DIR, 'pids', `celery_worker_${i + 1}.pid`)}`,

            // 进程配置
            interpreter: path.join(VENV_BIN, 'python'),
            exec_mode: "fork",
            instances: 1,

            // 自动重启配置
            autorestart: true,
            max_restarts: 10,
            min_uptime: "30s",
            restart_delay: 4000,
            exp_backoff_restart_delay: 100,

            // 内存限制：基础100MB + (2并发 × 200MB) = 500MB，留余量设 600MB
            max_memory_restart: "600M",

            // 日志配置
            error_file: path.join(LOGS_DIR, 'celery', `pm2_celery_worker_${i + 1}_error.log`),
            out_file: path.join(LOGS_DIR, 'celery', `pm2_celery_worker_${i + 1}_out.log`),
            log_file: path.join(LOGS_DIR, 'celery', `pm2_celery_worker_${i + 1}_combined.log`),
            combine_logs: true,
            merge_logs: true,

            // 日志轮转
            log_rotate_interval: "0 0 * * *",
            log_rotate_max_size: "100M",
            log_rotate_keep: 3,
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
            cwd: BASE_DIR,
        })),

        // Celery PDF Extractor Worker - 专门处理 PDF 提取任务
        {
            name: "celery_pdf_extractor",
            script: path.join(VENV_BIN, 'celery'),
            args: `-A backend.celery_pdf_extractor worker --pool=gevent --concurrency=1 --loglevel=info --max-memory-per-child=1200000 --max-tasks-per-child=200 --prefetch-multiplier=1 -n pdf_extractor@%(h)s --pidfile=${path.join(LOGS_DIR, 'pids', 'celery_pdf_extractor.pid')}`,

            // 进程配置
            interpreter: path.join(VENV_BIN, 'python'),
            exec_mode: "fork",
            instances: 1,

            // 自动重启配置
            autorestart: true,
            max_restarts: 10,
            min_uptime: "30s",
            restart_delay: 4000,
            exp_backoff_restart_delay: 100,

            // 内存限制：基础600MB + (1并发 × 200-400MB任务) = 800-1000MB，留余量设 1.2GB
            max_memory_restart: "1200M",

            // 日志配置
            error_file: path.join(LOGS_DIR, 'celery', 'pm2_celery_pdf_extractor_error.log'),
            out_file: path.join(LOGS_DIR, 'celery', 'pm2_celery_pdf_extractor_out.log'),
            log_file: path.join(LOGS_DIR, 'celery', 'pm2_celery_pdf_extractor_combined.log'),
            combine_logs: true,
            merge_logs: true,

            // 日志轮转
            log_rotate_interval: "0 0 * * *",
            log_rotate_max_size: "100M",
            log_rotate_keep: 3,
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
            cwd: BASE_DIR,
        },

        // Celery Beat 配置
        {
            name: "celery_beat",
            script: path.join(VENV_BIN, 'celery'),
            args: `-A backend beat --loglevel=warning --pidfile=${path.join(LOGS_DIR, 'pids', 'celerybeat.pid')}`,

            interpreter: path.join(VENV_BIN, 'python'),
            exec_mode: "fork",
            instances: 1,

            autorestart: true,
            max_restarts: 5,
            min_uptime: "60s",

            error_file: path.join(LOGS_DIR, 'celery', 'pm2_celery_beat_error.log'),
            out_file: path.join(LOGS_DIR, 'celery', 'pm2_celery_beat_out.log'),
            log_file: path.join(LOGS_DIR, 'celery', 'pm2_celery_beat_combined.log'),
            combine_logs: true,
            merge_logs: true,

            // 日志轮转
            log_rotate_interval: "0 0 * * *",
            log_rotate_max_size: "100M",
            log_rotate_keep: 3,
            log_rotate_compress: true,

            env: {
                C_FORCE_ROOT: "1",
                DJANGO_SETTINGS_MODULE: "backend.settings",
            },

            cwd: BASE_DIR,
        },
    ],
};
