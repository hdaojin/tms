"""日期展示：保留现有格式，仅在完整日期与时间之间允许换行。"""

from django import template
from django.utils.formats import localize
from django.utils.html import format_html_join

register = template.Library()


@register.filter(expects_localtime=True)
def keep_date_parts(value):
    """供已格式化文本或日期对象使用；每个空格分隔的片段保持完整。"""
    if value is None:
        return ""
    return format_html_join(
        " ", '<span class="date-part">{}</span>', ((part,) for part in str(localize(value)).split())
    )
