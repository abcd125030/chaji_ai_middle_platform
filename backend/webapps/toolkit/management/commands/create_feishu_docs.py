"""
批量将Markdown文件转换为飞书文档的管理命令

使用方式:
    # 转换单个文件
    python manage.py create_feishu_docs --path /path/to/file.md --user-id 123

    # 转换目录下所有MD文件
    python manage.py create_feishu_docs --path /path/to/dir --username admin

    # Dry-run模式（只打印将要处理的文件）
    python manage.py create_feishu_docs --path /path/to/dir --user-id 123 --dry-run

    # 不转移所有权（文档归属于飞书应用）
    python manage.py create_feishu_docs --path /path/to/file.md --no-transfer
"""
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model

from authentication.models import UserAccount
from webapps.toolkit.services.feishu_document.standalone_service import (
    StandaloneFeishuDocumentService
)

User = get_user_model()


class Command(BaseCommand):
    help = '批量将Markdown文件转换为飞书文档'

    def add_arguments(self, parser):
        """添加命令行参数"""
        # 用户标识参数（互斥组）
        user_group = parser.add_mutually_exclusive_group()
        user_group.add_argument(
            '--user-id',
            type=int,
            help='指定文档归属用户的ID'
        )
        user_group.add_argument(
            '--username',
            type=str,
            help='指定文档归属用户的用户名'
        )

        # 路径参数
        parser.add_argument(
            '--path',
            type=str,
            required=True,
            help='Markdown文件或目录的路径'
        )

        # 可选参数
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='测试模式，只打印将要处理的文件，不实际创建文档'
        )

        parser.add_argument(
            '--no-transfer',
            action='store_true',
            help='不转移文档所有权（文档归属于飞书应用）'
        )

        parser.add_argument(
            '--no-recursive',
            action='store_true',
            help='不递归处理子目录中的MD文件'
        )

    def handle(self, *args, **options):
        """命令主处理方法"""
        path = options['path']
        user_id = options.get('user_id')
        username = options.get('username')
        dry_run = options.get('dry_run', False)
        no_transfer = options.get('no_transfer', False)
        recursive = not options.get('no_recursive', False)

        if dry_run:
            self.stdout.write(self.style.WARNING('=== DRY-RUN 模式 ==='))

        # 1. 解析用户和飞书Open ID
        user = None
        open_id = None

        if not no_transfer:
            if user_id:
                user = self._get_user_by_id(user_id)
            elif username:
                user = self._get_user_by_username(username)

            if user:
                open_id = self._get_feishu_open_id(user)
                if open_id:
                    self.stdout.write(self.style.SUCCESS(
                        f"用户: {user.username}, 飞书Open ID: {open_id}"
                    ))
                else:
                    self.stdout.write(self.style.WARNING(
                        f"用户 {user.username} 未绑定飞书账号，文档将不转移所有权"
                    ))
            else:
                self.stdout.write(self.style.WARNING(
                    "未指定用户或用户不存在，文档将不转移所有权"
                ))
        else:
            self.stdout.write(self.style.WARNING("已禁用所有权转移"))

        # 2. 收集要处理的MD文件
        md_files = self._collect_markdown_files(path, recursive)

        if not md_files:
            raise CommandError(f"未找到Markdown文件: {path}")

        self.stdout.write(f"\n找到 {len(md_files)} 个Markdown文件:")
        for f in md_files:
            self.stdout.write(f"  - {f}")

        # 3. Dry-run模式下直接返回
        if dry_run:
            self.stdout.write(self.style.SUCCESS(
                f"\n[DRY-RUN] 将处理 {len(md_files)} 个文件"
            ))
            return

        # 4. 执行转换
        self.stdout.write(f"\n开始转换...")
        service = StandaloneFeishuDocumentService()

        success_count = 0
        fail_count = 0
        results = []

        for idx, md_file in enumerate(md_files, start=1):
            self.stdout.write(f"\n[{idx}/{len(md_files)}] 处理: {md_file}")

            result = service.convert_markdown_file(
                markdown_path=str(md_file),
                owner_open_id=open_id
            )

            results.append((md_file, result))

            if result.success:
                success_count += 1
                status = "所有权已转移" if result.owner_transferred else "所有权未转移"
                self.stdout.write(self.style.SUCCESS(
                    f"  成功: {result.document_url} ({status})"
                ))
            else:
                fail_count += 1
                self.stdout.write(self.style.ERROR(
                    f"  失败: {result.error_message}"
                ))

        # 5. 输出统计
        self.stdout.write("\n" + "=" * 50)
        self.stdout.write(self.style.SUCCESS(f"转换完成！"))
        self.stdout.write(f"成功: {success_count}")
        self.stdout.write(f"失败: {fail_count}")

        if fail_count > 0:
            self.stdout.write(self.style.ERROR("\n失败文件:"))
            for md_file, result in results:
                if not result.success:
                    self.stdout.write(f"  - {md_file}: {result.error_message}")

    def _get_user_by_id(self, user_id: int):
        """根据ID获取用户"""
        try:
            return User.objects.get(id=user_id)
        except User.DoesNotExist:
            raise CommandError(f"用户ID {user_id} 不存在")

    def _get_user_by_username(self, username: str):
        """根据用户名获取用户"""
        try:
            return User.objects.get(username=username)
        except User.DoesNotExist:
            raise CommandError(f"用户名 {username} 不存在")

    def _get_feishu_open_id(self, user) -> str:
        """获取用户的飞书Open ID"""
        feishu_account = UserAccount.objects.filter(
            user=user,
            provider='feishu',
            is_verified=True
        ).first()

        if feishu_account:
            return feishu_account.provider_account_id
        return None

    def _collect_markdown_files(self, path: str, recursive: bool) -> list:
        """收集要处理的Markdown文件"""
        target = Path(path)

        if not target.exists():
            raise CommandError(f"路径不存在: {path}")

        if target.is_file():
            if target.suffix.lower() in ['.md', '.markdown']:
                return [target]
            else:
                raise CommandError(f"文件不是Markdown格式: {path}")

        if target.is_dir():
            if recursive:
                return sorted(target.rglob('*.md'))
            else:
                return sorted(target.glob('*.md'))

        return []
