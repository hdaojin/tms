from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "只读预览反馈明确授权后，激活账号缺少的查看、提交、回复和附件能力。"

    def handle(self, *args, **options):
        required = {
            "view_feedback",
            "add_feedback",
            "add_feedbackreply",
            "view_feedbackattachment",
            "add_feedbackattachment",
        }
        users = (
            get_user_model()
            .objects.filter(is_active=True)
            .prefetch_related(
                "user_permissions__content_type",
                "groups__permissions__content_type",
            )
            .order_by("username")
        )
        affected = 0
        self.stdout.write("反馈访问影响预览（只读；仅检查激活账号的实际原生权限）")
        for user in users:
            if user.is_superuser:
                continue
            groups = list(user.groups.all())
            permissions = [
                *user.user_permissions.all(),
                *(permission for group in groups for permission in group.permissions.all()),
            ]
            granted = {
                permission.codename for permission in permissions if permission.content_type.app_label == "feedback"
            }
            missing = sorted(required - granted)
            if missing:
                affected += 1
                self.stdout.write(
                    f"{user.username} | 角色：{', '.join(group.name for group in groups) or '无'} | 缺少：{', '.join('feedback.' + code for code in missing)}"
                )
        self.stdout.write(
            f"受影响账号：{affected}。该结果不要求向所有账号补授；管理员按实际使用需求显式分配角色或权限包。"
        )
