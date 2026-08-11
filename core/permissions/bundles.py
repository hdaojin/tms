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
        description="查看用户列表、用户详情与角色列表。",
        permissions=(
            ("view_all_profiles", "accounts", "userprofile"),
        ),
    ),
    PermissionBundleSpec(
        code="standards.maintain_standard",
        name="维护标准体系",
        description="维护技能项目、能力领域、技能树版本和技能节点。",
        permissions=(
            ("view_skillproject", "standards", "skillproject"),
            ("add_skillproject", "standards", "skillproject"),
            ("change_skillproject", "standards", "skillproject"),
            ("view_capabilitydomain", "standards", "capabilitydomain"),
            ("add_capabilitydomain", "standards", "capabilitydomain"),
            ("change_capabilitydomain", "standards", "capabilitydomain"),
            ("view_skilltreeversion", "standards", "skilltreeversion"),
            ("add_skilltreeversion", "standards", "skilltreeversion"),
            ("change_skilltreeversion", "standards", "skilltreeversion"),
            ("view_skillnode", "standards", "skillnode"),
            ("add_skillnode", "standards", "skillnode"),
            ("change_skillnode", "standards", "skillnode"),
        ),
    ),
    PermissionBundleSpec(
        code="events.maintain_event",
        name="维护事件",
        description="维护赛事系列、赛事级别、事件、事件模块和参与人员。",
        permissions=(
            ("view_competitionseries", "events", "competitionseries"),
            ("add_competitionseries", "events", "competitionseries"),
            ("change_competitionseries", "events", "competitionseries"),
            ("view_competitionlevel", "events", "competitionlevel"),
            ("add_competitionlevel", "events", "competitionlevel"),
            ("change_competitionlevel", "events", "competitionlevel"),
            ("view_event", "events", "event"),
            ("add_event", "events", "event"),
            ("change_event", "events", "event"),
            ("view_eventmodule", "events", "eventmodule"),
            ("add_eventmodule", "events", "eventmodule"),
            ("change_eventmodule", "events", "eventmodule"),
            ("view_eventparticipant", "events", "eventparticipant"),
            ("add_eventparticipant", "events", "eventparticipant"),
            ("change_eventparticipant", "events", "eventparticipant"),
        ),
    ),
    PermissionBundleSpec(
        code="training.maintain_training",
        name="维护训练",
        description="维护训练周期、训练日志并导出训练日志归档。",
        permissions=(
            ("view_trainingcycle", "training", "trainingcycle"),
            ("add_trainingcycle", "training", "trainingcycle"),
            ("change_trainingcycle", "training", "trainingcycle"),
            ("view_traininglog", "training", "traininglog"),
            ("add_traininglog", "training", "traininglog"),
            ("change_traininglog", "training", "traininglog"),
            ("view_all_traininglog", "training", "traininglog"),
            ("export_traininglog_archive", "training", "traininglog"),
        ),
    ),
    PermissionBundleSpec(
        code="archives.maintain_archive",
        name="维护资料资产",
        description="维护资料资产、业务绑定和下载归档。",
        permissions=(
            ("view_archiveasset", "archives", "archiveasset"),
            ("add_archiveasset", "archives", "archiveasset"),
            ("change_archiveasset", "archives", "archiveasset"),
        ),
    ),
    PermissionBundleSpec(
        code="scoring.maintain_scoring",
        name="维护评分",
        description="导入评分表，维护参评对象和评分结果。",
        permissions=(
            ("view_scoringscheme", "scoring", "scoringscheme"),
            ("add_scoringscheme", "scoring", "scoringscheme"),
            ("change_scoringscheme", "scoring", "scoringscheme"),
            ("view_scoringparticipant", "scoring", "scoringparticipant"),
            ("add_scoringparticipant", "scoring", "scoringparticipant"),
            ("change_scoringparticipant", "scoring", "scoringparticipant"),
            ("view_scoringresult", "scoring", "scoringresult"),
            ("add_scoringresult", "scoring", "scoringresult"),
            ("change_scoringresult", "scoring", "scoringresult"),
        ),
    ),
    PermissionBundleSpec(
        code="examcontent.maintain_examcontent",
        name="维护试题结构",
        description="维护试题和结构化试题要求。",
        permissions=(
            ("view_exampaper", "examcontent", "exampaper"),
            ("add_exampaper", "examcontent", "exampaper"),
            ("change_exampaper", "examcontent", "exampaper"),
            ("view_examrequirement", "examcontent", "examrequirement"),
            ("add_examrequirement", "examcontent", "examrequirement"),
            ("change_examrequirement", "examcontent", "examrequirement"),
        ),
    ),
    PermissionBundleSpec(
        code="knowledge.maintain_knowledge",
        name="维护考点知识",
        description="维护考点证据、审核状态和技能映射。",
        permissions=(
            ("view_knowledgeevidence", "knowledge", "knowledgeevidence"),
            ("add_knowledgeevidence", "knowledge", "knowledgeevidence"),
            ("change_knowledgeevidence", "knowledge", "knowledgeevidence"),
            ("view_knowledgeevidenceskillmap", "knowledge", "knowledgeevidenceskillmap"),
            ("add_knowledgeevidenceskillmap", "knowledge", "knowledgeevidenceskillmap"),
            ("change_knowledgeevidenceskillmap", "knowledge", "knowledgeevidenceskillmap"),
            ("delete_knowledgeevidenceskillmap", "knowledge", "knowledgeevidenceskillmap"),
        ),
    ),
    PermissionBundleSpec(
        code="glossary.contribute_entries",
        name="贡献专业词条",
        description="提交专业词条提案，并维护本人待审核或已驳回的提案。",
        permissions=(
            ("view_glossaryentryproposal", "glossary", "glossaryentryproposal"),
            ("add_glossaryentryproposal", "glossary", "glossaryentryproposal"),
            ("change_glossaryentryproposal", "glossary", "glossaryentryproposal"),
        ),
    ),
    PermissionBundleSpec(
        code="glossary.manage_glossaries",
        name="管理专业词库",
        description="管理词库与正式词条、执行导入和审核，并查看全体学习统计。",
        permissions=(
            ("view_professionalglossary", "glossary", "professionalglossary"),
            ("add_professionalglossary", "glossary", "professionalglossary"),
            ("change_professionalglossary", "glossary", "professionalglossary"),
            ("view_glossaryentry", "glossary", "glossaryentry"),
            ("add_glossaryentry", "glossary", "glossaryentry"),
            ("change_glossaryentry", "glossary", "glossaryentry"),
            ("view_glossaryentryproposal", "glossary", "glossaryentryproposal"),
            ("change_glossaryentryproposal", "glossary", "glossaryentryproposal"),
            ("view_glossaryimport", "glossary", "glossaryimport"),
            ("add_glossaryimport", "glossary", "glossaryimport"),
            ("change_glossaryimport", "glossary", "glossaryimport"),
            ("view_all_study_statistics", "glossary", "studysession"),
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
