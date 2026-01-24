# core/tables.py
import django_tables2 as tables
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.middleware.csrf import get_token


class BaseDateColumn(tables.DateColumn):
    """自定义日期列，统一日期显示格式为 YYYY-MM-DD（补零）。"""

    def __init__(self, *args, **kwargs):
        # Django 日期格式: Y = 4位年, m = 月(补零), d = 日(补零)
        kwargs.setdefault("format", "Y-m-d")
        super().__init__(*args, **kwargs)


class BaseTable(tables.Table):
    class Meta:
        template_name = "django-tables2/table.html"
        empty_text = "暂无数据"
        row_attrs = {"class": "hover:bg-base-300"}
        attrs = {
            "class": "table w-full",
            "thead": {"class": "bg-base-300"},
            "tbody": {"class": ""},
            "th": {"class": "text-left whitespace-nowrap"},
            "td": {"class": "align-center"},
        }


class ActionsColumn(tables.Column):
    """通用操作列（DaisyUI 模态确认删除）。

    参数：
        view_url: 详情 named url（如 'app:model_detail'）
        delete_url: 删除 named url（如 'app:model_delete'）
    view_perm: 显示“查看”所需权限（默认不校验）
    delete_perm: 显示“删除”所需权限（默认不校验）
        pk_field: URL 主键字段名，默认 'pk'
    """

    def __init__(
        self,
        view_url: str | None = None,
        delete_url: str | None = None,
        view_perm: str | None = None,
        delete_perm: str | None = None,
        pk_field: str = "pk",
        verbose_name: str = "操作",
        orderable: bool = False,
        attrs: dict | None = None,
        **kwargs,
    ):
        kwargs.setdefault("verbose_name", verbose_name)
        kwargs.setdefault("orderable", orderable)
        kwargs.setdefault("empty_values", ())
        super().__init__(attrs=attrs, **kwargs)
        self.view_url = view_url
        self.delete_url = delete_url
        self.view_perm = view_perm
        self.delete_perm = delete_perm
        self.pk_field = pk_field

    def render(self, record, table=None, request=None, **kwargs):  # type: ignore[override]
        # 获取 request/user
        request = request or getattr(table, "request", None)
        user = getattr(request, "user", None)

        # 权限：未提供 view_perm/delete_perm 则默认显示按钮（安全由后端视图兜底）
        app_label = getattr(getattr(record, "_meta", None), "app_label", None)
        model_name = getattr(getattr(record, "_meta", None), "model_name", None)
        view_perm = self.view_perm   # None => 不限制查看
        delete_perm = self.delete_perm  # None => 不限制删除

        # URL 与主键
        pk = getattr(record, self.pk_field)
        parts: list[str] = []

        # 查看
        if self.view_url and (not view_perm or (user and user.has_perm(view_perm))):
            try:
                url = reverse(self.view_url, args=[pk])
                parts.append(f'<a class="btn btn-soft btn-primary btn-xs" href="{url}">查看</a>')
            except Exception:
                pass

        # 删除（弹窗确认）
        if self.delete_url and (not delete_perm or (user and user.has_perm(delete_perm))):
            try:
                del_url = reverse(self.delete_url, args=[pk])
                modal_id = f"modal-del-{app_label}-{model_name}-{pk}"
                csrf = get_token(request) if request else ""
                parts.append(
                    "".join([
                        f'<button class="btn btn-soft btn-error btn-xs" onclick="document.getElementById(\'{modal_id}\').showModal()">删除</button>',
                        f'<dialog id="{modal_id}" class="modal">',
                        '<div class="modal-box">',
                        '<h3 class="font-bold text-lg">确认删除</h3>',
                        '<p class="py-2">此操作不可撤销，确定要删除吗？</p>',
                        f'<form method="post" action="{del_url}">',
                        f'<input type="hidden" name="csrfmiddlewaretoken" value="{csrf}">',
                        '<div class="modal-action">',
                        '<button type="submit" class="btn btn-error">确认删除</button>',
                        f'<button type="button" class="btn" onclick="document.getElementById(\'{modal_id}\').close()">取消</button>',
                        '</div>',
                        '</form>',
                        '</div>',
                        '</dialog>',
                    ])
                )
            except Exception:
                pass

        return mark_safe(" ".join(parts)) if parts else ""


 
