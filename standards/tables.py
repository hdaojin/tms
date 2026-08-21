import django_tables2 as tables

from core.tables import ActionsColumn, BaseTable

from .models import SkillProject, SkillTreeVersion, WSOSVersion


class SkillProjectTable(BaseTable):
    is_default = tables.TemplateColumn(
        template_code='{% if record.is_default %}<span class="badge badge-primary">默认</span>{% else %}—{% endif %}',
        verbose_name="默认项目",
        orderable=False,
    )
    actions = ActionsColumn(
        "standards:project_detail", "standards:project_edit", edit_perm="standards.change_skillproject"
    )

    class Meta(BaseTable.Meta):
        model = SkillProject
        fields = ["code", "name", "short_name", "is_default", "is_active", "actions"]


class SkillTreeVersionTable(BaseTable):
    actions = ActionsColumn(
        "standards:tree_detail", "standards:tree_edit", edit_perm="standards.change_skilltreeversion"
    )

    class Meta(BaseTable.Meta):
        model = SkillTreeVersion
        fields = ["skill_project", "version", "name", "is_current", "actions"]


class WSOSVersionTable(BaseTable):
    actions = ActionsColumn("standards:wsos_detail", "standards:wsos_edit", edit_perm="standards.change_wsosversion")

    class Meta(BaseTable.Meta):
        model = WSOSVersion
        fields = ["skill_project", "code", "name", "is_current", "actions"]
