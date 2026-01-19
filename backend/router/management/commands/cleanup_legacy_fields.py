"""
清理旧的供应商字段，完全迁移到新的Vendor关联
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from router.models import VendorEndpoint, VendorAPIKey
from router.vendor_models import Vendor


class Command(BaseCommand):
    help = '清理旧的供应商字段'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='清空旧字段的值（保留字段但清空内容）'
        )
    
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('检查旧字段使用情况...'))
        
        # 统计仍在使用旧字段的记录
        endpoints_with_old = VendorEndpoint.objects.filter(
            vendor__isnull=True
        ).exclude(vendor_name__isnull=True)
        
        keys_with_old = VendorAPIKey.objects.filter(
            vendor__isnull=True
        ).exclude(vendor_name__isnull=True)
        
        self.stdout.write(f'仍使用旧字段的端点: {endpoints_with_old.count()}')
        self.stdout.write(f'仍使用旧字段的API密钥: {keys_with_old.count()}')
        
        if options['clear']:
            with transaction.atomic():
                # 清空已经有vendor关联的记录的旧字段
                updated_endpoints = VendorEndpoint.objects.filter(
                    vendor__isnull=False
                ).update(
                    vendor_name=None,
                    vendor_id_legacy=None
                )
                
                updated_keys = VendorAPIKey.objects.filter(
                    vendor__isnull=False
                ).update(
                    vendor_name=None,
                    vendor_id_legacy=None
                )
                
                self.stdout.write(self.style.SUCCESS(
                    f'清理完成：更新了 {updated_endpoints} 个端点，{updated_keys} 个API密钥'
                ))
        else:
            # 显示需要迁移的记录
            if endpoints_with_old.exists():
                self.stdout.write('\n需要迁移的端点:')
                for endpoint in endpoints_with_old[:5]:
                    self.stdout.write(f'  - {endpoint.vendor_name}: {endpoint.service_type}')
            
            if keys_with_old.exists():
                self.stdout.write('\n需要迁移的API密钥:')
                for key in keys_with_old[:5]:
                    self.stdout.write(f'  - {key.vendor_name}')
            
            if endpoints_with_old.exists() or keys_with_old.exists():
                self.stdout.write('\n运行 python manage.py migrate_vendors 来迁移这些记录')
                self.stdout.write('或运行 python manage.py cleanup_legacy_fields --clear 来清理旧字段')