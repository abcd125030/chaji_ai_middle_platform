"""
将现有的供应商数据迁移到新的Vendor表
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from router.models import VendorEndpoint, VendorAPIKey
from router.vendor_models import Vendor


class Command(BaseCommand):
    help = '将现有的供应商数据迁移到新的Vendor表'
    
    # 供应商映射关系
    VENDOR_MAPPING = {
        'openrouter': {
            'display_name': 'OpenRouter',
            'description': 'OpenRouter API服务提供商',
            'website': 'https://openrouter.ai',
            'supported_services': ['文本补全', '聊天对话', '函数调用'],
        },
        'frago': {
            'display_name': 'frago',
            'description': 'frago API服务提供商',
            'website': '',
            'supported_services': ['文本补全', '聊天对话'],
        },
        'chagee': {
            'display_name': '茶姬',
            'description': '茶姬API服务提供商',
            'website': '',
            'supported_services': ['文本补全', '聊天对话'],
        },
        'aliyun': {
            'display_name': '阿里云百炼大模型',
            'description': '阿里云百炼大模型服务',
            'website': 'https://bailian.console.aliyun.com',
            'supported_services': ['文本补全', '聊天对话', '向量嵌入', '文本理解'],
        },
    }
    
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('开始迁移供应商数据...'))
        
        with transaction.atomic():
            # 1. 创建Vendor记录
            vendors_created = 0
            vendor_map = {}
            
            for vendor_id, config in self.VENDOR_MAPPING.items():
                vendor, created = Vendor.objects.get_or_create(
                    vendor_id=vendor_id,
                    defaults={
                        'display_name': config['display_name'],
                        'description': config['description'],
                        'website': config['website'],
                        'supported_services': config['supported_services'],
                        'is_active': True,
                        'priority': 0,
                    }
                )
                vendor_map[vendor_id] = vendor
                if created:
                    vendors_created += 1
                    self.stdout.write(f"  创建供应商: {vendor.display_name}")
                else:
                    self.stdout.write(f"  供应商已存在: {vendor.display_name}")
            
            self.stdout.write(self.style.SUCCESS(f'创建了 {vendors_created} 个新供应商'))
            
            # 2. 更新VendorEndpoint记录
            endpoints_updated = 0
            # 根据vendor_name匹配
            vendor_name_map = {
                'OpenRouter': 'openrouter',
                'frago': 'frago',
                '茶姬': 'chagee',
                '阿里云百炼大模型': 'aliyun',
            }
            
            for endpoint in VendorEndpoint.objects.filter(vendor__isnull=True):
                vendor_name = endpoint.vendor_name
                if vendor_name and vendor_name in vendor_name_map:
                    vendor_id = vendor_name_map[vendor_name]
                    if vendor_id in vendor_map:
                        endpoint.vendor = vendor_map[vendor_id]
                        endpoint.save()
                        endpoints_updated += 1
                        self.stdout.write(f"  更新端点: {endpoint}")
            
            self.stdout.write(self.style.SUCCESS(f'更新了 {endpoints_updated} 个端点'))
            
            # 3. 更新VendorAPIKey记录
            keys_updated = 0
            for api_key in VendorAPIKey.objects.filter(vendor__isnull=True):
                vendor_name = api_key.vendor_name
                if vendor_name and vendor_name in vendor_name_map:
                    vendor_id = vendor_name_map[vendor_name]
                    if vendor_id in vendor_map:
                        api_key.vendor = vendor_map[vendor_id]
                        api_key.save()
                        keys_updated += 1
                        self.stdout.write(f"  更新API密钥: {api_key}")
            
            self.stdout.write(self.style.SUCCESS(f'更新了 {keys_updated} 个API密钥'))
            
        self.stdout.write(self.style.SUCCESS('供应商数据迁移完成！'))
        
        # 显示迁移统计
        self.stdout.write('\n迁移统计：')
        for vendor in Vendor.objects.all():
            endpoints_count = vendor.endpoints.count()
            keys_count = vendor.api_keys.count()
            self.stdout.write(
                f"  {vendor.display_name}: {endpoints_count} 个端点, {keys_count} 个API密钥"
            )