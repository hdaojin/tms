"""评测资料的命名、输入校验与版本读取。"""

import re
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db.models import Max

from core.code_validators import assessment_code_validator, module_code_validator, project_code_validator

from .models import AssessmentDocument


DOCUMENT_FILENAME_TYPES = {
    "test_project": "TestProject",
    "marking_standard": "MarkingScheme",
    "technical_description": "TechnicalDescription",
    "scoring_script": "ScoringScript",
    "result_file": "ResultFile",
    "attachment": "Attachment",
}


def parse_document_version(value):
    if not re.fullmatch(r"[0-9]{1,8}\.[0-9]", str(value)):
        raise ValidationError("版本须为一位小数的数字，例如 1.0；整数部分最多 8 位，不含 v 前缀。")
    version = Decimal(value)
    if version < Decimal("1.0"):
        raise ValidationError("版本不能小于 1.0。")
    return version


def latest_document_version(assessment_id, module_id, document_type):
    return AssessmentDocument.objects.filter(
        assessment_id=assessment_id,
        module_id=module_id,
        document_type=document_type,
    ).aggregate(latest=Max("numeric_version"))["latest"]


def validate_document_upload(assessment, module, document_type, version):
    errors = {}
    for field, code, validator in (
        ("assessment", assessment.code, assessment_code_validator),
        ("assessment", assessment.skill_project.code, project_code_validator),
        ("module", module.code if module else "A", module_code_validator),
    ):
        try:
            validator(code)
        except ValidationError as exc:
            errors.setdefault(field, []).extend([f"{message}请联系管理员检查历史代码。" for message in exc.messages])
    if module and module.assessment_id != assessment.pk:
        errors["module"] = ["评测模块必须属于当前竞赛与考核。"]
    if document_type not in DOCUMENT_FILENAME_TYPES:
        errors["document_type"] = ["请选择有效的资料类型。"]
    try:
        numeric = parse_document_version(version)
    except ValidationError as exc:
        errors["version"] = exc.messages
    else:
        latest = latest_document_version(assessment.pk, module.pk if module else None, document_type)
        if latest is not None and numeric <= latest:
            errors["version"] = [f"当前最高版本为 {latest:.1f}，新版本必须更大。"]
    if errors:
        raise ValidationError(errors)
    return numeric
