# common/tables.py
import django_tables2 as tables


class BaseTable(tables.Table):
    class Meta:
        template_name = "django_tables2/table.html"
        empty_text = "暂无数据"
        row_attrs = { "class": "hover:bg-base-300" }
        attrs = {
            "class": "table w-full",
            "thead": {"class": "bg-base-300"},
            "tbody": {"class": ""},
            "th": {"class": "text-left whitespace-nowrap"},
            "td": {"class": "align-center"},
        }