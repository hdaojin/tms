from django_tables2 import Column, TemplateColumn

from core.tables import BaseTable


class ModelTable(BaseTable):
    class Meta(BaseTable.Meta):
        pass

    name = TemplateColumn(
        template_code="""
        {% if record.can_manage_record %}<a class="link link-hover" href="{% url 'ai:detail' record.pk %}">{{ record.name }}</a>
        {% else %}{{ record.name }}{% endif %}
        <div class="text-sm text-base-content/70 break-all">{{ record.model_id }}</div>
        """,
        verbose_name="模型名称",
    )
    provider = Column(accessor="provider_label", order_by="provider", verbose_name="模型提供商")
    owner = Column(accessor="owner__display_name", orderable=False, verbose_name="所有者")
    verified = TemplateColumn(
        template_code="""
        {% if record.verified %}已验证{% else %}待验证{% endif %}
        {% if record.can_manage_record and record.test_error %}<div class="text-warning">最近测试失败</div>{% endif %}
        """,
        verbose_name="验证状态",
    )
    sharing = TemplateColumn(
        template_code="""
        {% if record.is_delisted %}已下架{% elif record.is_shared %}{{ record.get_share_audience_display }}
        {% else %}私有{% endif %}
        """,
        verbose_name="共享范围",
        order_by=("is_delisted", "is_shared", "share_audience"),
    )
    actions = TemplateColumn(
        template_code='{% include "ai/default_action.html" with model=record %}',
        verbose_name="默认模型",
        orderable=False,
    )
