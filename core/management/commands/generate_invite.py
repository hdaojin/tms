from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from accounts.services.registration import DEFAULT_INVITATION_HOURS, issue_registration_invitation


class Command(BaseCommand):
    help = "为新用户生成注册邀请码"

    def add_arguments(self, parser):
        parser.add_argument("--actor-id", type=int, required=True, help="签发人的超级管理员用户 ID")
        parser.add_argument("--count", type=int, default=1, help="生成的邀请码数量")
        parser.add_argument("--hours", type=int, default=DEFAULT_INVITATION_HOURS, help="每个邀请码的有效小时数")
        parser.add_argument("--max-uses", type=int, default=1, help="每个邀请码的注册名额")

    def handle(self, *args, **options):
        actor = get_user_model().objects.filter(
            pk=options["actor_id"], is_active=True, is_superuser=True,
        ).first()
        if actor is None:
            raise CommandError("签发人必须是有效的超级管理员。")
        if options["count"] < 1:
            raise CommandError("邀请码数量至少为 1。")

        for _ in range(options["count"]):
            try:
                _, code = issue_registration_invitation(
                    actor=actor, hours=options["hours"], max_uses=options["max_uses"],
                )
            except ValidationError as error:
                raise CommandError(error.messages[0]) from error
            self.stdout.write(code)
