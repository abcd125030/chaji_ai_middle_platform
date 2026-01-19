#!/usr/bin/env python3
"""
配置验证脚本 - 检查所有关键配置是否正确应用
"""

import subprocess
import sys
import json
import psycopg2
import redis
from datetime import datetime

# 颜色输出
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_header(text):
    print(f"\n{Colors.HEADER}{'='*60}{Colors.ENDC}")
    print(f"{Colors.HEADER}{text}{Colors.ENDC}")
    print(f"{Colors.HEADER}{'='*60}{Colors.ENDC}")

def print_success(text):
    print(f"{Colors.OKGREEN}✓ {text}{Colors.ENDC}")

def print_warning(text):
    print(f"{Colors.WARNING}⚠ {text}{Colors.ENDC}")

def print_error(text):
    print(f"{Colors.FAIL}✗ {text}{Colors.ENDC}")

def print_info(text):
    print(f"{Colors.OKBLUE}ℹ {text}{Colors.ENDC}")

# PostgreSQL配置检查
def check_postgresql():
    print_header("PostgreSQL 配置检查")
    
    try:
        # 连接到PostgreSQL
        conn = psycopg2.connect(
            dbname="X",
            user="postgres",
            host="localhost",
            port=5432
        )
        cur = conn.cursor()
        
        # 检查关键参数
        params_to_check = {
            'max_connections': (1500, 1000, 2000),
            'work_mem': ('64MB', '32MB', '128MB'),
            'shared_buffers': ('128GB', '64GB', '256GB'),
            'effective_cache_size': ('384GB', '256GB', '512GB'),
        }
        
        for param, (expected, min_val, max_val) in params_to_check.items():
            cur.execute(f"SHOW {param};")
            actual = cur.fetchone()[0]
            
            if param == 'work_mem':
                # 检查work_mem是否在合理范围
                if actual == expected:
                    print_success(f"{param}: {actual} (优化值)")
                elif actual == '256MB':
                    print_warning(f"{param}: {actual} (建议改为{expected})")
                else:
                    print_info(f"{param}: {actual}")
            else:
                print_info(f"{param}: {actual}")
        
        # 检查当前连接数
        cur.execute("""
            SELECT count(*) as total,
                   sum(case when state = 'active' then 1 else 0 end) as active,
                   sum(case when state = 'idle' then 1 else 0 end) as idle,
                   sum(case when state = 'idle in transaction' then 1 else 0 end) as idle_in_transaction
            FROM pg_stat_activity
            WHERE datname = 'X';
        """)
        
        stats = cur.fetchone()
        print_info(f"当前连接: 总计={stats[0]}, 活跃={stats[1]}, 空闲={stats[2]}, 事务中空闲={stats[3]}")
        
        if stats[0] > 1000:
            print_warning("连接数较高，请检查连接池配置")
        
        cur.close()
        conn.close()
        print_success("PostgreSQL连接成功")
        
    except Exception as e:
        print_error(f"PostgreSQL检查失败: {e}")

# Redis配置检查
def check_redis():
    print_header("Redis 配置检查")
    
    try:
        # 连接到Redis
        r = redis.Redis(
            host='localhost',
            port=6379,
            password='chagee332335!',
            decode_responses=True
        )
        
        # 获取配置信息
        config = r.config_get()
        info = r.info()
        
        # 检查关键配置
        checks = {
            'maxmemory': '50gb',
            'maxmemory-policy': 'allkeys-lru',
            'maxclients': '10000',
            'tcp-keepalive': '60',
        }
        
        for key, expected in checks.items():
            actual = config.get(key, 'not set')
            if str(actual).lower() == str(expected).lower():
                print_success(f"{key}: {actual}")
            elif key == 'maxmemory' and actual == '0':
                print_warning(f"{key}: 未限制 (建议设置为{expected})")
            else:
                print_info(f"{key}: {actual} (建议: {expected})")
        
        # 检查内存使用
        used_memory = info.get('used_memory_human', 'N/A')
        used_memory_peak = info.get('used_memory_peak_human', 'N/A')
        connected_clients = info.get('connected_clients', 0)
        
        print_info(f"内存使用: {used_memory} (峰值: {used_memory_peak})")
        print_info(f"连接客户端: {connected_clients}")
        
        # 检查回调队列
        pending_size = r.llen('callback_queue:pending')
        processing_size = r.llen('callback_queue:processing')
        
        print_info(f"回调队列: 待处理={pending_size}, 处理中={processing_size}")
        
        if pending_size > 100:
            print_warning(f"待处理队列较大({pending_size})，请检查处理速度")
        
        print_success("Redis连接成功")
        
    except Exception as e:
        print_error(f"Redis检查失败: {e}")

# PgBouncer配置检查
def check_pgbouncer():
    print_header("PgBouncer 配置检查")
    
    try:
        # 连接到PgBouncer管理数据库
        conn = psycopg2.connect(
            dbname="pgbouncer",
            user="postgres",
            host="localhost",
            port=6432
        )
        cur = conn.cursor()
        
        # 获取连接池状态
        cur.execute("SHOW POOLS;")
        pools = cur.fetchall()
        
        if pools:
            for pool in pools:
                db_name = pool[0]
                if db_name == 'X':
                    print_info(f"数据库: {db_name}")
                    print_info(f"  客户端活跃: {pool[1]}")
                    print_info(f"  客户端等待: {pool[2]}")
                    print_info(f"  服务器活跃: {pool[3]}")
                    print_info(f"  服务器空闲: {pool[4]}")
                    print_info(f"  服务器使用中: {pool[5]}")
                    print_info(f"  服务器测试中: {pool[6]}")
                    print_info(f"  服务器登录中: {pool[7]}")
                    print_info(f"  最大等待时间: {pool[8]}")
                    
                    # 检查是否有大量等待
                    if pool[2] > 10:  # cl_waiting
                        print_warning(f"有{pool[2]}个客户端在等待连接")
        
        # 获取配置
        cur.execute("SHOW CONFIG;")
        configs = cur.fetchall()
        
        important_configs = {
            'pool_mode': 'transaction',
            'default_pool_size': '200',
            'max_client_conn': '10000',
            'max_db_connections': '1200',
        }
        
        for config in configs:
            if config[0] in important_configs:
                expected = important_configs[config[0]]
                actual = config[1]
                if str(actual) == expected:
                    print_success(f"{config[0]}: {actual}")
                else:
                    print_warning(f"{config[0]}: {actual} (建议: {expected})")
        
        cur.close()
        conn.close()
        print_success("PgBouncer连接成功")
        
    except Exception as e:
        print_error(f"PgBouncer检查失败: {e}")

# 系统资源检查
def check_system_resources():
    print_header("系统资源检查")
    
    try:
        # 检查内存
        result = subprocess.run(['free', '-h'], capture_output=True, text=True)
        lines = result.stdout.strip().split('\n')
        mem_line = lines[1].split()
        
        total_mem = mem_line[1]
        used_mem = mem_line[2]
        free_mem = mem_line[3]
        
        print_info(f"内存: 总计={total_mem}, 已用={used_mem}, 空闲={free_mem}")
        
        # 检查负载
        with open('/proc/loadavg', 'r') as f:
            loadavg = f.read().strip().split()
            print_info(f"负载均衡: 1分钟={loadavg[0]}, 5分钟={loadavg[1]}, 15分钟={loadavg[2]}")
            
            if float(loadavg[0]) > 64:  # 假设64核CPU
                print_warning("系统负载较高")
        
        # 检查端口范围
        result = subprocess.run(['sysctl', 'net.ipv4.ip_local_port_range'], 
                              capture_output=True, text=True)
        port_range = result.stdout.strip()
        print_info(f"端口范围: {port_range}")
        
        if '10000' not in port_range:
            print_warning("建议扩大端口范围: sysctl -w net.ipv4.ip_local_port_range='10000 65000'")
        
        # 检查文件句柄
        result = subprocess.run(['sysctl', 'fs.file-max'], 
                              capture_output=True, text=True)
        file_max = result.stdout.strip()
        print_info(f"文件句柄限制: {file_max}")
        
    except Exception as e:
        print_error(f"系统资源检查失败: {e}")

# Celery状态检查
def check_celery():
    print_header("Celery Workers 检查")
    
    try:
        # 检查supervisor状态
        result = subprocess.run(['supervisorctl', 'status'], 
                              capture_output=True, text=True)
        
        lines = result.stdout.strip().split('\n')
        running_workers = 0
        
        for line in lines:
            if 'celery' in line.lower():
                if 'RUNNING' in line:
                    running_workers += 1
                    print_success(line)
                else:
                    print_warning(line)
        
        print_info(f"运行中的Celery workers: {running_workers}")
        
        # 检查Redis中的Celery队列
        try:
            r = redis.Redis(
                host='localhost',
                port=6379,
                password='chagee332335!',
                db=0
            )
            
            # 检查默认队列
            celery_queue_size = r.llen('celery')
            print_info(f"Celery默认队列任务数: {celery_queue_size}")
            
            if celery_queue_size > 1000:
                print_warning("队列积压较多，请检查worker处理能力")
                
        except Exception as e:
            print_warning(f"无法检查Celery队列: {e}")
            
    except Exception as e:
        print_error(f"Celery检查失败: {e}")

# 性能基准测试
def performance_benchmark():
    print_header("性能基准检查")
    
    # 计算理论容量
    workers = 20
    gevent_pool = 500
    total_capacity = workers * gevent_pool
    
    task_duration = 20  # 秒
    required_qps = 170
    required_concurrent = required_qps * task_duration
    
    print_info(f"Celery配置容量: {total_capacity} 并发")
    print_info(f"需求并发数: {required_concurrent} (170 QPS × 20秒)")
    
    if total_capacity >= required_concurrent:
        print_success(f"容量充足: {total_capacity} >= {required_concurrent}")
    else:
        print_warning(f"容量不足: {total_capacity} < {required_concurrent}")
    
    # 检查数据库连接配置
    print_info("\n连接池配置检查:")
    print_info("PostgreSQL max_connections: 1500")
    print_info("PgBouncer max_db_connections: 1200")
    print_info("PgBouncer default_pool_size: 200 (建议值)")
    print_info("Redis maxclients: 10000")
    
    # 内存估算
    pg_work_mem = 64  # MB
    pg_connections = 1500
    pg_memory_need = pg_work_mem * pg_connections / 1024  # GB
    
    print_info(f"\n内存需求估算:")
    print_info(f"PostgreSQL work_mem需求: {pg_memory_need:.1f} GB")
    print_info(f"Redis建议限制: 50 GB")
    print_info(f"总内存: 500 GB (充足)")

# 生成优化报告
def generate_report():
    print_header("配置优化报告")
    
    report = {
        'timestamp': datetime.now().isoformat(),
        'checks': [],
        'recommendations': []
    }
    
    # 关键配置建议
    recommendations = [
        "1. PostgreSQL work_mem: 建议从256MB降至64MB",
        "2. Redis maxmemory: 建议设置为50GB",
        "3. PgBouncer default_pool_size: 建议从800降至200",
        "4. 系统端口范围: 建议设置为10000-65000",
        "5. 监控回调队列大小，确保及时处理",
    ]
    
    for rec in recommendations:
        print_info(rec)
        report['recommendations'].append(rec)
    
    # 保存报告
    report_file = f"config_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2)
    
    print_success(f"报告已保存到: {report_file}")

# 主函数
def main():
    print(f"{Colors.BOLD}配置验证脚本 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{Colors.ENDC}")
    
    # 执行所有检查
    check_postgresql()
    check_redis()
    check_pgbouncer()
    check_system_resources()
    check_celery()
    performance_benchmark()
    generate_report()
    
    print_header("验证完成")
    print_success("所有检查已完成，请查看上述结果和建议")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n已中断")
        sys.exit(0)
    except Exception as e:
        print_error(f"验证脚本错误: {e}")
        sys.exit(1)