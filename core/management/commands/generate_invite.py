"""
Management command to generate invitation codes
用法：
  uv run manage.py generate_invite
  uv run manage.py generate_invite --count 5

安全说明：
  - 使用 Django signing.dumps() 生成安全邀请码
  - 基于 HMAC-SHA256 签名，无法伪造
  - 包含时间戳，自动过期验证
"""
from django.core.management.base import BaseCommand
from core.utils.invitation import generate_invitation_code


class Command(BaseCommand):
    help = '生成邀请码供新用户注册使用'

    def add_arguments(self, parser):
        parser.add_argument(
            '--count',
            type=int,
            default=1,
            help='生成邀请码的数量（默认：1）'
        )

    def handle(self, *args, **options):
        count = options['count']
        
        self.stdout.write(self.style.SUCCESS(f'\n正在生成 {count} 个邀请码...\n'))
        
        for i in range(count):
            code = generate_invitation_code()
            self.stdout.write(f'{i+1}. {code}')
        
        self.stdout.write(self.style.SUCCESS('\n✓ 生成完成！\n'))
        self.stdout.write('说明：')
        self.stdout.write('  - 请将邀请码完整复制给用户（不要手动输入）')
        self.stdout.write('  - 邀请码有效期：24小时')
        self.stdout.write('  - 使用 Django 签名技术，安全可靠\n')
