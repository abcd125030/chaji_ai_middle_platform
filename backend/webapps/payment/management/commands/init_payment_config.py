from django.core.management.base import BaseCommand
from webapps.payment.models import PaymentConfig
import os


class Command(BaseCommand):
    help = '初始化支付配置'

    def handle(self, *args, **options):
        # 检查是否已存在配置
        if PaymentConfig.objects.filter(provider='hupijiao').exists():
            self.stdout.write(self.style.WARNING('虎皮椒支付配置已存在，跳过创建'))
            return
        
        # 创建虎皮椒支付配置
        config = PaymentConfig.objects.create(
            provider='hupijiao',
            app_id=os.getenv('HUPIJIAO_APP_ID', 'test_app_id'),
            app_secret=os.getenv('HUPIJIAO_APP_SECRET', 'test_app_secret'),
            api_url='https://api.xunhupay.com/payment/do.html',
            is_active=True,
            is_test_mode=True,
            extra_config={
                'timeout': 30,
                'max_retries': 3,
                'comment': '测试环境配置，请在生产环境修改为实际的应用ID和密钥'
            }
        )
        
        self.stdout.write(self.style.SUCCESS(f'成功创建虎皮椒支付配置：{config}'))
        self.stdout.write(self.style.WARNING('请登录Django管理后台修改为实际的应用ID和密钥'))