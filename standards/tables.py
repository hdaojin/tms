import django_tables2 as tables

from core.tables import ActionsColumn, BaseDateTimeColumn, BaseTable

from .models import SkillProject, SkillTreeNode, SkillTreeVersion, WSOSVersion


class SuperuserActionsColumn(ActionsColumn):
    """查看操作保持原样，治理类编辑操作仅向 superuser 展示。"""

    def _has_perm(self, user, perm):
        if perm is None:
            return True
        return bool(user and user.is_superuser)


class SkillProjectTable(BaseTable):
    is_default = tables.TemplateColumn(
        template_code='{% if record.is_default %}<span class="badge badge-primary">默认</span>{% else %}—{% endif %}',
        verbose_name="默认项目",
        orderable=False,
    )
    actions = SuperuserActionsColumn(
        "standards:project_detail", "standards:project_edit", edit_perm="standards.change_skillproject"
    )

    class Meta(BaseTable.Meta):
        model = SkillProject
        fields = ["code", "name", "short_name", "is_default", "is_active", "actions"]


class SkillTreeVersionTable(BaseTable):
    skill_project = tables.Column(
        accessor="technical_domain__skill_project",
        verbose_name="技能项目",
        order_by=("technical_domain__skill_project__code", "technical_domain__skill_project__name"),
    )
    technical_domain = tables.Column(verbose_name="技术领域")
    updated_at = BaseDateTimeColumn(verbose_name="更新时间")
    actions = SuperuserActionsColumn(
        "standards:tree_detail", "standards:tree_edit", edit_perm="standards.change_skilltreeversion"
    )

    class Meta(BaseTable.Meta):
        model = SkillTreeVersion
        fields = ["skill_project", "technical_domain", "version", "name", "is_current", "updated_at", "actions"]


class SkillTreeNodeTable(BaseTable):
    skill = tables.Column(
        accessor="skill__name",
        verbose_name="技能名称",
        linkify=lambda record: ("standards:skill_detail", [record.skill_id]),
        order_by=("skill__name",),
    )
    full_path = tables.Column(verbose_name="完整路径", orderable=False)
    difficulty = tables.Column(accessor="skill__difficulty", verbose_name="难度", order_by=("skill__difficulty",))
    is_core = tables.BooleanColumn(accessor="skill__is_core", verbose_name="核心技能", order_by=("skill__is_core",))
    is_assessable = tables.BooleanColumn(
        accessor="skill__is_assessable",
        verbose_name="可考核",
        order_by=("skill__is_assessable",),
    )
    is_active = tables.BooleanColumn(
        accessor="skill__is_active", verbose_name="启用状态", order_by=("skill__is_active",)
    )
    current_wsos_mapping = tables.TemplateColumn(
        template_code=(
            '{% if record.current_wsos_unavailable %}尚未设置当前 WSOS'
            '{% elif record.has_current_wsos_mapping %}<span class="badge badge-success">已映射</span>'
            '{% else %}<span class="badge badge-ghost">未映射</span>{% endif %}'
        ),
        verbose_name="当前 WSOS 映射",
        orderable=False,
    )
    updated_at = BaseDateTimeColumn(
        accessor="skill__updated_at",
        verbose_name="更新时间",
        order_by=("skill__updated_at",),
    )
    actions = tables.TemplateColumn(
        template_code=(
            '<div class="flex justify-center gap-2">'
            '<a class="btn btn-xs btn-soft btn-primary" href="{% url \'standards:skill_detail\' record.skill_id %}">查看</a>'
            '{% if record.can_edit_skill %}'
            '<a class="btn btn-xs btn-soft btn-warning" href="{% url \'standards:tree_node_skill_edit\' record.tree_version_id record.pk %}">编辑</a>'
            '{% endif %}'
            '</div>'
        ),
        verbose_name="操作",
        orderable=False,
    )

    class Meta(BaseTable.Meta):
        model = SkillTreeNode
        fields = [
            "skill",
            "full_path",
            "difficulty",
            "is_core",
            "is_assessable",
            "is_active",
            "current_wsos_mapping",
            "updated_at",
            "actions",
        ]


class WSOSVersionTable(BaseTable):
    actions = SuperuserActionsColumn(
        "standards:wsos_detail",
        "standards:wsos_edit",
        edit_perm="standards.change_wsosversion",
    )

    class Meta(BaseTable.Meta):
        model = WSOSVersion
        fields = ["skill_project", "code", "name", "is_current", "actions"]
