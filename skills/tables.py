import django_tables2 as tables

from core.utils.tables import BaseTable
from .models import Skill


class SkillTable(BaseTable):
    project = tables.Column(verbose_name="标准赛项", accessor="topic.module.project.name")
    module = tables.Column(verbose_name="标准模块", accessor="topic.module")
    topic = tables.Column(verbose_name="专题", accessor="topic.name")
    exam_point_count = tables.Column(verbose_name="关联考点数", empty_values=(), orderable=False)

    def render_description(self, value):
        return value or "-"

    def render_exam_point_count(self, record):
        return getattr(record, 'exam_point_count', 0)

    class Meta(BaseTable.Meta):
        model = Skill
        fields = ('project', 'module', 'topic', 'name', 'description', 'exam_point_count')
        order_by = ('topic__module__project__name', 'topic__module__code', 'topic__name', 'name')