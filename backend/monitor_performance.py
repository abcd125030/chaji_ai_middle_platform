#!/usr/bin/env python
"""
性能监控脚本 - 实时监控系统瓶颈
"""
import psutil
import psycopg2
import redis
import time
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

def get_db_stats():
    """获取数据库连接统计"""
    try:
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST", "localhost"),
            port=os.getenv("DB_PORT", "5432"),
            database=os.getenv("DB_DATABASE", "X"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", "")
        )
        cur = conn.cursor()
        
        # 活跃连接数
        cur.execute("""
            SELECT count(*) as active_connections,
                   sum(CASE WHEN state = 'active' THEN 1 ELSE 0 END) as active_queries,
                   sum(CASE WHEN state = 'idle' THEN 1 ELSE 0 END) as idle_connections,
                   sum(CASE WHEN state = 'idle in transaction' THEN 1 ELSE 0 END) as idle_in_transaction
            FROM pg_stat_activity
            WHERE datname = %s;
        """, (os.getenv("DB_DATABASE", "X"),))
        
        stats = cur.fetchone()
        
        # 慢查询
        cur.execute("""
            SELECT count(*) 
            FROM pg_stat_activity 
            WHERE state = 'active' 
                AND query_start < NOW() - INTERVAL '1 second'
                AND datname = %s;
        """, (os.getenv("DB_DATABASE", "X"),))
        
        slow_queries = cur.fetchone()[0]
        
        cur.close()
        conn.close()
        
        return {
            "active_connections": stats[0],
            "active_queries": stats[1],
            "idle_connections": stats[2],
            "idle_in_transaction": stats[3],
            "slow_queries": slow_queries
        }
    except Exception as e:
        print(f"Database stats error: {e}")
        return None

def get_pgbouncer_stats():
    """获取 PgBouncer 统计"""
    try:
        conn = psycopg2.connect(
            host="localhost",
            port="6432",
            database="pgbouncer",
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", "")
        )
        cur = conn.cursor()
        
        # 获取池统计
        cur.execute("SHOW POOLS;")
        pools = cur.fetchall()
        
        # 获取统计信息
        cur.execute("SHOW STATS;")
        stats = cur.fetchall()
        
        cur.close()
        conn.close()
        
        pool_info = {}
        for pool in pools:
            if pool[0] == os.getenv("DB_DATABASE", "X"):
                pool_info = {
                    "client_active": pool[2],
                    "client_waiting": pool[3],
                    "server_active": pool[4],
                    "server_idle": pool[5],
                    "server_used": pool[6],
                    "server_login": pool[8],
                    "max_wait": pool[9]
                }
                break
        
        return pool_info
    except Exception as e:
        print(f"PgBouncer stats error: {e}")
        return None

def get_redis_stats():
    """获取 Redis 统计"""
    try:
        r = redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", "6379")),
            password=os.getenv("REDIS_PASSWORD"),
            decode_responses=True
        )
        
        info = r.info()
        return {
            "connected_clients": info.get("connected_clients", 0),
            "used_memory_human": info.get("used_memory_human", "N/A"),
            "instantaneous_ops_per_sec": info.get("instantaneous_ops_per_sec", 0),
            "keyspace_hits": info.get("keyspace_hits", 0),
            "keyspace_misses": info.get("keyspace_misses", 0),
        }
    except Exception as e:
        print(f"Redis stats error: {e}")
        return None

def get_system_stats():
    """获取系统资源使用情况"""
    return {
        "cpu_percent": psutil.cpu_percent(interval=1),
        "memory_percent": psutil.virtual_memory().percent,
        "disk_io_read": psutil.disk_io_counters().read_bytes,
        "disk_io_write": psutil.disk_io_counters().write_bytes,
        "network_sent": psutil.net_io_counters().bytes_sent,
        "network_recv": psutil.net_io_counters().bytes_recv
    }

def monitor_loop():
    """主监控循环"""
    print("=" * 80)
    print(f"Performance Monitor Started - {datetime.now()}")
    print("=" * 80)
    
    while True:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 收集统计信息
        db_stats = get_db_stats()
        pgbouncer_stats = get_pgbouncer_stats()
        redis_stats = get_redis_stats()
        system_stats = get_system_stats()
        
        # 输出报告
        print(f"\n[{timestamp}] Performance Report")
        print("-" * 60)
        
        if db_stats:
            print(f"PostgreSQL:")
            print(f"  Active Connections: {db_stats['active_connections']}")
            print(f"  Active Queries: {db_stats['active_queries']}")
            print(f"  Idle Connections: {db_stats['idle_connections']}")
            print(f"  Idle in Transaction: {db_stats['idle_in_transaction']}")
            print(f"  Slow Queries (>1s): {db_stats['slow_queries']}")
            
            # 瓶颈警告
            if db_stats['active_queries'] > 50:
                print(f"  ⚠️  WARNING: High active queries!")
            if db_stats['idle_in_transaction'] > 10:
                print(f"  ⚠️  WARNING: Many idle transactions!")
        
        if pgbouncer_stats:
            print(f"\nPgBouncer:")
            print(f"  Client Active: {pgbouncer_stats.get('client_active', 0)}")
            print(f"  Client Waiting: {pgbouncer_stats.get('client_waiting', 0)}")
            print(f"  Server Active: {pgbouncer_stats.get('server_active', 0)}")
            print(f"  Server Idle: {pgbouncer_stats.get('server_idle', 0)}")
            print(f"  Max Wait Time: {pgbouncer_stats.get('max_wait', 0)}")
            
            # 瓶颈警告
            if pgbouncer_stats.get('client_waiting', 0) > 10:
                print(f"  ⚠️  WARNING: Clients waiting for connections!")
        
        if redis_stats:
            print(f"\nRedis:")
            print(f"  Connected Clients: {redis_stats['connected_clients']}")
            print(f"  Memory Used: {redis_stats['used_memory_human']}")
            print(f"  Operations/sec: {redis_stats['instantaneous_ops_per_sec']}")
        
        print(f"\nSystem:")
        print(f"  CPU Usage: {system_stats['cpu_percent']}%")
        print(f"  Memory Usage: {system_stats['memory_percent']}%")
        
        # 瓶颈分析
        print("\n" + "=" * 60)
        if db_stats and db_stats['active_queries'] > 50:
            print("🔴 DATABASE BOTTLENECK DETECTED!")
        elif pgbouncer_stats and pgbouncer_stats.get('client_waiting', 0) > 10:
            print("🟡 CONNECTION POOL BOTTLENECK!")
        elif system_stats['cpu_percent'] > 80:
            print("🟡 HIGH CPU USAGE!")
        elif system_stats['memory_percent'] > 80:
            print("🟡 HIGH MEMORY USAGE!")
        else:
            print("🟢 System running normally")
        
        # 等待下一次检查
        time.sleep(5)

if __name__ == "__main__":
    try:
        monitor_loop()
    except KeyboardInterrupt:
        print("\nMonitoring stopped.")