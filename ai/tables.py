from django.template.loader import render_to_string
from django_tables2 import Column, TemplateColumn

from core.tables import BaseTable

from .catalog import provider_logos
from .providers import provider_display_name


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
    provider = Column(verbose_name="模型提供商")
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

    def __init__(self, *args, provider_labels, **kwargs):
        super().__init__(*args, **kwargs)
        self.provider_labels = provider_labels
        self.provider_logos = provider_logos(provider_labels)

    def render_provider(self, value, record):
        return render_to_string("ai/provider_name.html", {
            "label": provider_display_name(value, record.custom_provider_name, self.provider_labels),
            "branding": self.provider_logos.get(value),
        })

    def value_provider(self, value, record):
        return provider_display_name(value, record.custom_provider_name, self.provider_labels)


class ProviderTable(BaseTable):
    class Meta(BaseTable.Meta):
        orderable = False

    display_order = Column(verbose_name="显示顺序")
    provider = TemplateColumn(
        template_code="""<a class="link link-hover" href="{% url 'ai:provider' record.code %}">
          {% include "ai/provider_name.html" with label=record.label branding=record.branding only %}
        </a>""",
        verbose_name="提供商",
    )
    provider_key = Column(verbose_name="Provider Key")
    protocol = Column(verbose_name="API 协议")
    default_url = TemplateColumn(
        template_code='<span class="break-all">{{ record.default_url|default:"未设置" }}</span>',
        verbose_name="默认 API 地址",
    )
    default_model_label = TemplateColumn(
        template_code="""
        {{ record.default_model_label|default:"未指定" }}
        {% if record.default_model_label and record.default_model_label != record.default_model %}
          <div class="text-sm text-base-content/70 break-all">{{ record.default_model }}</div>
        {% endif %}
        """,
        verbose_name="默认模型",
    )
    model_count = Column(verbose_name="可选模型（数量）")
    enabled = TemplateColumn(
        template_code="{% if record.enabled %}已启用{% else %}已停用{% endif %}",
        verbose_name="状态",
    )

    def render_model_count(self, value):
        return f"{value} 个"
