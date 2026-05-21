from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from django.contrib.auth.models import Permission


PermissionSpec = tuple[str, str, str]


@dataclass(frozen=True)
class PermissionBundleSpec:
    code: str
    name: str
    description: str
    permissions: tuple[PermissionSpec, ...]

    @property
    def permission_labels(self) -> tuple[str, ...]:
        return tuple(f"{app_label}.{codename}" for codename, app_label, _model in self.permissions)


PERMISSION_BUNDLE_SPECS = (
    PermissionBundleSpec(
        code="behaviors.record_conduct",
        name="录入奖惩记录",
        description="录入奖惩记录，并自动补齐记录列表与汇总所需查看权限。",
        permissions=(
            ("add_conduct_record", "behaviors", "conductrecord"),
            ("view_all_conduct_records", "behaviors", "conductrecord"),
            ("view_conductrecord", "behaviors", "conductrecord"),
            ("view_conductsummary", "behaviors", "conductsummary"),
        ),
    ),
    PermissionBundleSpec(
        code="behaviors.review_conduct",
        name="审核奖惩记录",
        description="审核奖惩记录，并自动补齐记录列表与汇总所需查看权限。",
        permissions=(
            ("review_conduct_record", "behaviors", "conductrecord"),
            ("view_all_conduct_records", "behaviors", "conductrecord"),
            ("view_conductrecord", "behaviors", "conductrecord"),
            ("view_conductsummary", "behaviors", "conductsummary"),
        ),
    ),
    PermissionBundleSpec(
        code="behaviors.view_all_conduct_records",
        name="查看全部奖惩记录",
        description="查看全部奖惩记录与奖惩汇总。",
        permissions=(
            ("view_all_conduct_records", "behaviors", "conductrecord"),
            ("view_conductrecord", "behaviors", "conductrecord"),
            ("view_conductsummary", "behaviors", "conductsummary"),
        ),
    ),
    PermissionBundleSpec(
        code="meetings.upload_meeting",
        name="上传会议记录",
        description="上传会议记录，并授予会议记录新增权限。",
        permissions=(
            ("add_meeting", "meetings", "meeting"),
        ),
    ),
    PermissionBundleSpec(
        code="meetings.delete_meeting",
        name="删除会议记录",
        description="删除会议记录，并授予会议记录删除权限。",
        permissions=(
            ("delete_meeting", "meetings", "meeting"),
        ),
    ),
    PermissionBundleSpec(
        code="notices.publish_notice",
        name="发布通知",
        description="发布通知公告，并授予通知新增权限。",
        permissions=(
            ("add_notice", "notices", "notice"),
        ),
    ),
    PermissionBundleSpec(
        code="accounts.view_all_profiles",
        name="查看全部用户资料",
        description="查看用户列表与用户详情。",
        permissions=(
            ("view_all_profiles", "accounts", "userprofile"),
        ),
    ),
    PermissionBundleSpec(
        code="assessments.view_all_scores",
        name="查看全部考核成绩",
        description="查看全部考核详情与成绩。",
        permissions=(
            ("view_all_scores", "assessments", "assessment"),
        ),
    ),
    PermissionBundleSpec(
        code="competitions.link_member",
        name="关联代表队",
        description="关联或新增代表队，并授予代表队新增权限。",
        permissions=(
            ("add_member", "competitions", "member"),
        ),
    ),
    PermissionBundleSpec(
        code="competitions.create_competitor",
        name="新增选手",
        description="新增竞赛选手，并授予选手新增权限。",
        permissions=(
            ("add_competitor", "competitions", "competitor"),
        ),
    ),
    PermissionBundleSpec(
        code="competitions.create_expert",
        name="新增专家",
        description="新增竞赛专家，并授予专家新增权限。",
        permissions=(
            ("add_expert", "competitions", "expert"),
        ),
    ),
    PermissionBundleSpec(
        code="competitions.create_skillposition",
        name="新增岗位人员",
        description="新增竞赛岗位人员，并授予岗位人员新增权限。",
        permissions=(
            ("add_skillposition", "competitions", "skillposition"),
        ),
    ),
    PermissionBundleSpec(
        code="competitions.record_competition_result",
        name="录入竞赛总成绩",
        description="录入竞赛总成绩，并授予竞赛成绩新增权限。",
        permissions=(
            ("add_competitionresult", "competitions", "competitionresult"),
        ),
    ),
    PermissionBundleSpec(
        code="traininglogs.upload_traininglog",
        name="上传训练日志",
        description="上传训练日志，并自动补齐训练日志模型查看权限。",
        permissions=(
            ("add_traininglog", "traininglogs", "traininglog"),
            ("view_traininglog", "traininglogs", "traininglog"),
        ),
    ),
    PermissionBundleSpec(
        code="traininglogs.view_coach_traininglogs",
        name="查看教练训练日志",
        description="查看教练训练日志列表与详情，并自动补齐训练日志模型查看权限。",
        permissions=(
            ("view_coach_traininglog", "traininglogs", "traininglog"),
            ("view_traininglog", "traininglogs", "traininglog"),
        ),
    ),
    PermissionBundleSpec(
        code="traininglogs.view_competitor_traininglogs",
        name="查看选手训练日志",
        description="查看选手训练日志列表与详情，并自动补齐训练日志模型查看权限。",
        permissions=(
            ("view_competitor_traininglog", "traininglogs", "traininglog"),
            ("view_traininglog", "traininglogs", "traininglog"),
        ),
    ),
    PermissionBundleSpec(
        code="traininglogs.view_all_traininglogs",
        name="查看全部训练日志",
        description="查看全部训练日志列表与详情，并自动补齐训练日志相关查看权限。",
        permissions=(
            ("view_all_traininglog", "traininglogs", "traininglog"),
            ("view_coach_traininglog", "traininglogs", "traininglog"),
            ("view_competitor_traininglog", "traininglogs", "traininglog"),
            ("view_traininglog", "traininglogs", "traininglog"),
        ),
    ),
)


PERMISSION_BUNDLE_SPEC_MAP = {spec.code: spec for spec in PERMISSION_BUNDLE_SPECS}


def get_permission_bundle_specs() -> tuple[PermissionBundleSpec, ...]:
    return PERMISSION_BUNDLE_SPECS


def get_permission_bundle_choices() -> list[tuple[str, str]]:
    return [(spec.code, spec.name) for spec in PERMISSION_BUNDLE_SPECS]


def normalize_permission_bundle_codes(bundle_codes: Iterable[str] | None) -> list[str]:
    normalized: list[str] = []
    for code in bundle_codes or []:
        if code in PERMISSION_BUNDLE_SPEC_MAP and code not in normalized:
            normalized.append(code)
    return normalized


def get_permissions_for_bundle_codes(bundle_codes: Iterable[str] | None):
    permission_ids: set[int] = set()
    for code in normalize_permission_bundle_codes(bundle_codes):
        spec = PERMISSION_BUNDLE_SPEC_MAP[code]
        for codename, app_label, model_name in spec.permissions:
            permission_id = (
                Permission.objects.filter(
                    codename=codename,
                    content_type__app_label=app_label,
                    content_type__model=model_name,
                )
                .values_list("id", flat=True)
                .first()
            )
            if permission_id is not None:
                permission_ids.add(permission_id)

    if not permission_ids:
        return Permission.objects.none()

    return Permission.objects.filter(id__in=permission_ids).select_related("content_type")