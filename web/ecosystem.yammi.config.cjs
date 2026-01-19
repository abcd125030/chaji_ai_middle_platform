module.exports = {
  apps: [
    {
      name: 'chagee-studio-yammi',
      script: '.next/standalone/server.js',
      instances: 1,
      exec_mode: 'cluster',
      autorestart: true,
      watch: false,
      max_memory_restart: '2G',

      // 日志配置
      error_file: '/home/yammi/下载/Repos/X/web/logs/pm2/pm2-studio-yammi-err.log',
      out_file: '/home/yammi/下载/Repos/X/web/logs/pm2/pm2-studio-yammi-out.log',
      log_file: '/home/yammi/下载/Repos/X/web/logs/pm2/pm2-studio-yammi-combined.log',
      combine_logs: true,
      merge_logs: true,

      // 日志旋转配置
      log_rotate_interval: '0 0 * * *',
      log_rotate_max_size: '100M',
      log_rotate_keep: 7,
      log_rotate_compress: true,

      // 监控和重启配置
      max_restarts: 5,
      min_uptime: '10s',
      restart_delay: 2000,
      exp_backoff_restart_delay: 100,

      // PID 文件路径
      pid_file: '/home/yammi/下载/Repos/X/web/logs/pids/studio-yammi.pid',

      // 工作目录
      cwd: '/home/yammi/下载/Repos/X/web',

      env: {
        PORT: 3000,
        HOSTNAME: '0.0.0.0',
        NODE_ENV: 'test',
      },
    }
  ]
}