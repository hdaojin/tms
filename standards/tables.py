import django_tables2 as tables

from core.tables import ActionsColumn, BaseTable

from .models import Skill, SkillProject, SkillTreeVersion, WSOSVersion


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


class SkillTable(BaseTable):
    name = tables.TemplateColumn(
        template_code="""
        <div class="min-w-48 text-left">
          <a class="link link-primary font-medium" href="{% url 'standards:skill_detail' record.pk %}">{{ record.name }}</a>
          {% if record.aliases %}<p class="mt-1 text-xs text-base-content/60">别名：{{ record.aliases|join:'、' }}</p>{% endif %}
        </div>
        """,
        verbose_name="技能名称",
    )
    relationship = tables.TemplateColumn(
        template_code="""
        {% if record.is_related_match %}
          <div class="min-w-28 text-left">
            <span class="badge badge-info badge-sm">关联技能</span>
            <p class="mt-1 text-xs text-base-content/60">主要归属：{{ record.primary_domain.name }}</p>
          </div>
        {% else %}
          <span class="badge badge-ghost badge-sm">主要技能</span>
        {% endif %}
        """,
        verbose_name="领域关系",
        orderable=False,
    )
    description = tables.TemplateColumn(
        template_code='<p class="max-w-80 text-left text-sm">{{ record.description|default:"—"|truncatechars:80 }}</p>',
        verbose_name="描述",
        orderable=False,
    )
    actions = tables.TemplateColumn(
        template_code="""
        <div class="flex justify-center gap-1">
          <a class="btn btn-soft btn-primary btn-xs" href="{% url 'standards:skill_detail' record.pk %}">查看</a>
          {% if perms.standards.change_skill and record.can_edit_skill %}
            <a class="btn btn-soft btn-warning btn-xs" href="{% url 'standards:skill_edit' record.pk %}">编辑</a>
          {% endif %}
        </div>
        """,
        verbose_name="操作",
        orderable=False,
    )

    class Meta(BaseTable.Meta):
        model = Skill
        fields = [
            "name",
            "relationship",
            "description",
            "difficulty",
            "is_core",
            "is_active",
            "actions",
        ]
        row_attrs = {
            "id": lambda record: f"skill-row-{record.pk}",
            "class": lambda record: (
                "scroll-mt-24 bg-success/10 outline outline-2 outline-success/40"
                if getattr(record, "is_highlighted", False)
                else "hover:bg-base-200"
            ),
            "data-scroll-after-swap": lambda record: "true" if getattr(record, "is_highlighted", False) else None,
        }


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
