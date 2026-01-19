#!/usr/bin/env python
"""
服务器端查询 ImageEditTask 错误统计脚本

使用方法:
1. 将此文件上传到服务器的 Django 项目目录
2. 在服务器上运行:
   python manage.py shell < server_query_errors.py
   
或者在 Django shell 中直接导入运行:
   python manage.py shell
   >>> from customized.image_editor.server_query_errors import run_query
   >>> run_query()
"""
from customized.image_editor.models import ImageEditTask
from django.db.models import Q, Count, F
from datetime import datetime, timedelta
import json


def analyze_error_patterns():
    """分析错误模式并提供详细统计"""
    
    print("\n" + "=" * 80)
    print("ImageEditTask 错误详情统计分析")
    print("=" * 80)
    
    # 基础统计
    total_tasks = ImageEditTask.objects.count()
    processing_tasks = ImageEditTask.objects.filter(status='processing').count()
    success_tasks = ImageEditTask.objects.filter(status='success').count()
    failed_tasks = ImageEditTask.objects.filter(status='failed').count()
    
    print(f"\n📊 任务状态统计:")
    print(f"  总任务数: {total_tasks}")
    print(f"  处理中: {processing_tasks}")
    print(f"  成功: {success_tasks}")
    print(f"  失败: {failed_tasks}")
    if total_tasks > 0:
        print(f"  失败率: {failed_tasks/total_tasks*100:.2f}%")
    
    # 关键错误类型统计
    print(f"\n🔍 关键错误类型统计:")
    
    # port=443 相关错误（连接错误）
    port_443_errors = ImageEditTask.objects.filter(
        error_details__icontains='port=443'
    )
    port_443_count = port_443_errors.count()
    print(f"\n  1. 包含 'port=443' 的错误（连接错误）: {port_443_count}")
    
    if port_443_count > 0:
        # 获取样例
        sample = port_443_errors.first()
        if sample and sample.error_details:
            print(f"     样例错误详情前200字符:")
            print(f"     {sample.error_details[:200]}...")
    
    # 429 错误（速率限制）
    error_429 = ImageEditTask.objects.filter(
        Q(error_details__icontains='429') | 
        Q(error_message__icontains='429') |
        Q(error_code='429')
    )
    error_429_count = error_429.count()
    print(f"\n  2. 包含 '429' 的错误（速率限制）: {error_429_count}")
    
    if error_429_count > 0:
        # 获取样例
        sample = error_429.first()
        if sample:
            print(f"     样例错误信息:")
            if sample.error_code:
                print(f"     错误码: {sample.error_code}")
            if sample.error_message:
                print(f"     错误消息: {sample.error_message[:100]}...")
            if sample.error_details:
                print(f"     错误详情前200字符: {sample.error_details[:200]}...")
    
    # 时间分布分析
    print(f"\n📅 时间分布分析:")
    
    # 最近24小时
    one_day_ago = datetime.now() - timedelta(days=1)
    recent_24h_443 = ImageEditTask.objects.filter(
        created_at__gte=one_day_ago,
        error_details__icontains='port=443'
    ).count()
    recent_24h_429 = ImageEditTask.objects.filter(
        created_at__gte=one_day_ago,
        error_details__icontains='429'
    ).count()
    
    print(f"  过去24小时:")
    print(f"    port=443 错误: {recent_24h_443}")
    print(f"    429 错误: {recent_24h_429}")
    
    # 最近7天
    seven_days_ago = datetime.now() - timedelta(days=7)
    recent_7d_443 = ImageEditTask.objects.filter(
        created_at__gte=seven_days_ago,
        error_details__icontains='port=443'
    ).count()
    recent_7d_429 = ImageEditTask.objects.filter(
        created_at__gte=seven_days_ago,
        error_details__icontains='429'
    ).count()
    
    print(f"  过去7天:")
    print(f"    port=443 错误: {recent_7d_443}")
    print(f"    429 错误: {recent_7d_429}")
    
    # 其他常见错误模式
    print(f"\n🔧 其他错误模式统计:")
    
    # 超时错误
    timeout_errors = ImageEditTask.objects.filter(
        Q(error_details__icontains='timeout') | 
        Q(error_details__icontains='timed out') |
        Q(error_message__icontains='timeout')
    ).count()
    print(f"  超时错误: {timeout_errors}")
    
    # 连接错误（除了port=443）
    connection_errors = ImageEditTask.objects.filter(
        Q(error_details__icontains='connection') |
        Q(error_details__icontains='connect') |
        Q(error_message__icontains='connection')
    ).exclude(error_details__icontains='port=443').count()
    print(f"  其他连接错误: {connection_errors}")
    
    # SSL/TLS 错误
    ssl_errors = ImageEditTask.objects.filter(
        Q(error_details__icontains='ssl') |
        Q(error_details__icontains='tls') |
        Q(error_message__icontains='ssl')
    ).count()
    print(f"  SSL/TLS 错误: {ssl_errors}")
    
    # 网络错误
    network_errors = ImageEditTask.objects.filter(
        Q(error_details__icontains='network') |
        Q(error_message__icontains='network')
    ).count()
    print(f"  网络错误: {network_errors}")
    
    # API 错误
    api_errors = ImageEditTask.objects.filter(
        Q(error_details__icontains='api') |
        Q(error_message__icontains='api')
    ).count()
    print(f"  API 错误: {api_errors}")
    
    # 返回统计结果
    return {
        'total_tasks': total_tasks,
        'failed_tasks': failed_tasks,
        'port_443_errors': port_443_count,
        'error_429': error_429_count,
        'recent_24h_443': recent_24h_443,
        'recent_24h_429': recent_24h_429,
        'recent_7d_443': recent_7d_443,
        'recent_7d_429': recent_7d_429,
        'timeout_errors': timeout_errors,
        'connection_errors': connection_errors,
        'ssl_errors': ssl_errors
    }


def get_error_samples(limit=5):
    """获取错误样例供分析"""
    print(f"\n📝 错误样例（最近{limit}条）:")
    print("-" * 80)
    
    # 获取最近的失败任务
    recent_failures = ImageEditTask.objects.filter(
        status='failed'
    ).exclude(
        error_details__isnull=True
    ).exclude(
        error_details=''
    ).order_by('-created_at')[:limit]
    
    for idx, task in enumerate(recent_failures, 1):
        print(f"\n样例 {idx}:")
        print(f"  Task ID: {task.task_id}")
        print(f"  创建时间: {task.created_at}")
        print(f"  错误码: {task.error_code or 'N/A'}")
        print(f"  错误消息: {task.error_message[:100] if task.error_message else 'N/A'}...")
        
        # 检查是否包含特定错误模式
        if task.error_details:
            patterns = []
            if 'port=443' in task.error_details:
                patterns.append('port=443')
            if '429' in task.error_details:
                patterns.append('429')
            if 'timeout' in task.error_details.lower():
                patterns.append('timeout')
            if 'connection' in task.error_details.lower():
                patterns.append('connection')
            
            if patterns:
                print(f"  包含模式: {', '.join(patterns)}")
            
            print(f"  错误详情前300字符:")
            print(f"  {task.error_details[:300]}...")
        print("-" * 40)


def export_error_data():
    """导出错误数据供进一步分析"""
    print("\n💾 导出错误数据...")
    
    # 导出包含 port=443 的错误
    port_443_tasks = ImageEditTask.objects.filter(
        error_details__icontains='port=443'
    ).values('task_id', 'created_at', 'error_code', 'error_message')[:10]
    
    # 导出包含 429 的错误
    error_429_tasks = ImageEditTask.objects.filter(
        error_details__icontains='429'
    ).values('task_id', 'created_at', 'error_code', 'error_message')[:10]
    
    export_data = {
        'port_443_errors': list(port_443_tasks),
        'error_429': list(error_429_tasks),
        'export_time': datetime.now().isoformat()
    }
    
    # 保存到文件
    with open('error_analysis_export.json', 'w', encoding='utf-8') as f:
        json.dump(export_data, f, indent=2, default=str, ensure_ascii=False)
    
    print(f"  数据已导出到 error_analysis_export.json")
    print(f"  包含 port=443 错误: {len(export_data['port_443_errors'])} 条")
    print(f"  包含 429 错误: {len(export_data['error_429'])} 条")


def run_query():
    """主函数：运行所有查询"""
    try:
        # 运行分析
        stats = analyze_error_patterns()
        
        # 获取错误样例
        get_error_samples(limit=5)
        
        # 导出数据（可选）
        # export_error_data()
        
        # 打印总结
        print("\n" + "=" * 80)
        print("📊 统计总结")
        print("=" * 80)
        print(f"总任务数: {stats['total_tasks']}")
        print(f"失败任务数: {stats['failed_tasks']}")
        print(f"包含 port=443 的错误: {stats['port_443_errors']}")
        print(f"包含 429 的错误: {stats['error_429']}")
        print(f"过去24小时 port=443 错误: {stats['recent_24h_443']}")
        print(f"过去24小时 429 错误: {stats['recent_24h_429']}")
        print("=" * 80)
        
        return stats
        
    except Exception as e:
        print(f"\n❌ 查询出错: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


# 如果直接在 Django shell 中运行
if __name__ == '__main__' or 'django' in globals():
    run_query()