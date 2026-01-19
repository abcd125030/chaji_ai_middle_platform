from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken, BlacklistedToken
from django.utils import timezone
from datetime import timedelta

User = get_user_model()


class Command(BaseCommand):
    help = '使指定用户的 JWT token 立即过期（用于测试）'

    def add_arguments(self, parser):
        parser.add_argument('username', type=str, help='用户名')
        parser.add_argument(
            '--expire-in',
            type=int,
            default=0,
            help='多少秒后过期（默认立即过期）'
        )

    def handle(self, *args, **options):
        username = options['username']
        expire_in = options['expire_in']
        
        try:
            user = User.objects.get(username=username)
            
            # 获取用户的所有未过期 token
            outstanding_tokens = OutstandingToken.objects.filter(
                user=user,
                expires_at__gt=timezone.now()
            )
            
            if not outstanding_tokens.exists():
                self.stdout.write(
                    self.style.WARNING(f'用户 {username} 没有有效的 token')
                )
                return
            
            # 修改 token 的过期时间
            new_expire_time = timezone.now() + timedelta(seconds=expire_in)
            for token in outstanding_tokens:
                token.expires_at = new_expire_time
                token.save()
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Token {token.token[:20]}... 将在 {new_expire_time} 过期'
                    )
                )
            
            if expire_in == 0:
                self.stdout.write(
                    self.style.SUCCESS(f'用户 {username} 的所有 token 已立即过期')
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'用户 {username} 的所有 token 将在 {expire_in} 秒后过期'
                    )
                )
                
        except User.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'用户 {username} 不存在')
            )