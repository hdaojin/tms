import django_tables2 as tables

from core.tables import ActionsColumn, BaseTable

from .models import CapabilityDomain, SkillNode, SkillProject, SkillTreeVersion


class SkillProjectTable(BaseTable):
    actions = ActionsColumn(view_url="standards:project_detail", edit_url="standards:project_edit")

    class Meta(BaseTable.Meta):
        model = SkillProject
        fields = ("code", "name", "short_name", "is_active", "actions")


class CapabilityDomainTable(BaseTable):
    actions = ActionsColumn(view_url="standards:domain_detail", edit_url="standards:domain_edit")

    class Meta(BaseTable.Meta):
        model = CapabilityDomain
        fields = ("skill_project", "code", "name", "is_active", "actions")


class SkillTreeVersionTable(BaseTable):
    actions = ActionsColumn(view_url="standards:tree_detail", edit_url="standards:tree_edit")

    class Meta(BaseTable.Meta):
        model = SkillTreeVersion
        fields = ("skill_project", "version", "name", "is_current", "actions")


class SkillNodeTable(BaseTable):
    path = tables.Column(verbose_name="路径", orderable=False)
    actions = ActionsColumn(view_url="standards:node_detail", edit_url="standards:node_edit")

    class Meta(BaseTable.Meta):
        model = SkillNode
        fields = ("capability_domain", "code", "name", "node_type", "is_active", "path", "actions")

    def render_path(self, record):
        return record.get_full_path()
