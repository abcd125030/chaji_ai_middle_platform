module.exports = {
  apps: [
    {
      name: 'frago-studio',
      script: '.next/standalone/server.js',
      instances: 4,  // 优化：从10个实例降至4个，匹配4核CPU
      exec_mode: 'cluster',
      autorestart: true,
      watch: false,
      max_memory_restart: '1500M',  // 优化：降低内存限制，更合理分配资源
      
      // 日志配置
      error_file: '/www/wwwroot/github/X/web/logs/pm2/pm2-studio-err.log',
      out_file: '/www/wwwroot/github/X/web/logs/pm2/pm2-studio-out.log',
      log_file: '/www/wwwroot/github/X/web/logs/pm2/pm2-studio-combined.log',
      combine_logs: true,
      merge_logs: true,
      
      // 日志旋转配置
      log_rotate_interval: '0 0 * * *',
      log_rotate_max_size: '300M',
      log_rotate_keep: 14,
      log_rotate_compress: true,
      
      // 监控和重启配置
      max_restarts: 10,
      min_uptime: '30s',
      restart_delay: 4000,
      exp_backoff_restart_delay: 100,
      
      // PID 文件路径
      pid_file: '/www/wwwroot/github/X/web/logs/pids/studio.pid',

      env: {
        PORT: 3323,
        HOSTNAME: '0.0.0.0',
        NODE_ENV: 'production',
        // NEXT_PUBLIC_BASE_PATH: '/_studio',
      },
    }
  ]
}
