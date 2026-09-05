"""用于文件命名的业务代码输入规则。"""

from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError


def validate_immutable_code(instance):
    """已有对象的代码是稳定身份；不依赖是否已产生资料。"""
    if instance.pk is None:
        return
    original = (
        type(instance)._base_manager.using(instance._state.db)
        .filter(pk=instance.pk).values_list("code", flat=True).first()
    )
    if original is not None and instance.code != original:
        raise ValidationError({"code": "代码创建后不可修改，请通过名称调整显示内容。"})


assessment_code_validator = RegexValidator(r"\A[A-Za-z0-9]{1,20}\Z", "评测代码须为 1–20 位英文字母或数字。")
project_code_validator = RegexValidator(r"\A[A-Za-z0-9]{1,12}\Z", "技能项目代码须为 1–12 位英文字母或数字。")
module_code_validator = RegexValidator(
    r"\A(?![Gg][Ee][Nn]\Z)[A-Za-z0-9]{1,8}\Z", "模块代码须为 1–8 位英文字母或数字，不能使用保留值 GEN。"
)
