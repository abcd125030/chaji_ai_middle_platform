# 保存为 fix_config.sh

  echo "开始修复配置..."

  # PostgreSQL修复
  echo "1. 修复PostgreSQL work_mem..."
  sudo -u postgres /www/server/pgsql/bin/psql -h localhost -p 5432 -c "ALTER SYSTEM SET work_mem = '64MB';" 2>/dev/null || {
      echo "  使用配置文件方式..."
      sudo sed -i 's/work_mem = 256MB/work_mem = 64MB/' /www/server/pgsql/data/postgresql.conf
  }

  # 重载PostgreSQL
  echo "2. 重载PostgreSQL..."
  /etc/init.d/pgsql reload || sudo -u postgres /www/server/pgsql/bin/pg_ctl reload -D /www/server/pgsql/data

  # Redis修复
  echo "3. 修复Redis内存限制..."
  /www/server/redis/src/redis-cli -a 'chagee332335!' CONFIG SET maxmemory 50gb
  /www/server/redis/src/redis-cli -a 'chagee332335!' CONFIG SET maxmemory-policy allkeys-lru
  /www/server/redis/src/redis-cli -a 'chagee332335!' CONFIG REWRITE

  # 验证
  echo "4. 验证配置..."
  echo -n "PostgreSQL work_mem: "
  sudo -u postgres /www/server/pgsql/bin/psql -h localhost -p 5432 -t -c "SHOW work_mem;" 2>/dev/null

  echo -n "Redis maxmemory: "
  /www/server/redis/src/redis-cli -a 'chagee332335!' CONFIG GET maxmemory 2>/dev/null | tail -1

  echo "修复完成！"