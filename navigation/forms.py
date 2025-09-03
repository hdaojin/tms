# navigation/forms.py
from django import forms
from django.urls import get_resolver
from django.contrib.auth.models import Permission
from django.contrib.admin.widgets import FilteredSelectMultiple
from .models import MenuItem

def discover_named_urls():
    """递归遍历 URLPattern/URLResolver 获取命名路由名称（含命名空间前缀）。

    示例输出： articles:list / meeting:meeting_detail / accounts:login
    过滤掉： admin / navigation / common 命名空间及后台自动生成的管理端增删改列表路由。
    """
    resolver = get_resolver()
    collected = set()

    def walk(patterns, namespaces=None):
        if namespaces is None:
            namespaces = []
        for p in patterns:
            if hasattr(p, 'url_patterns'):
                ns = getattr(p, 'namespace', None)
                # 如果此 resolver 有 namespace，则加入栈
                if ns:
                    walk(p.url_patterns, namespaces + [ns])  # type: ignore
                else:
                    walk(p.url_patterns, namespaces)  # type: ignore
            else:
                nm = getattr(p, 'name', None)
                if not nm:
                    continue
                full = ':'.join(namespaces + [nm]) if namespaces else nm
                # 顶层命名空间过滤
                top_ns = full.split(':', 1)[0]
                if top_ns in {'admin', 'navigation', 'common'}:
                    continue
                base = full.split(':')[-1]
                if base in {'app_list','index','autocomplete','login','logout','password_change','password_change_done','jsi18n','view_on_site'}:
                    # login/logout 可考虑保留，如需保留在上面集合移除
                    pass
                # 过滤后台典型后缀（针对 base 名称）
                if any(base.endswith(suf) for suf in ('_add','_change','_delete','_history','_changelist')):
                    return
                collected.add(full)

    walk(resolver.url_patterns)
    result = sorted(collected)
    # home 放最前（若存在且无命名空间）
    if 'home' in result:
        result.remove('home')
        result.insert(0, 'home')
    return result


class MenuItemForm(forms.ModelForm):
    # 初始只放一个空选项；实际候选在 __init__ 中动态填充
    named_url = forms.ChoiceField(
        label="命名路由",
        required=False,
        choices=[("", "——（不使用命名路由）——")],
    )

    permissions = forms.ModelMultipleChoiceField(
        label="所需权限",
        required=False,
        queryset=Permission.objects.select_related("content_type").order_by(
            "content_type__app_label", "codename"
        ),
        widget=FilteredSelectMultiple("权限", is_stacked=False),
        help_text="按住 Control 键或 Mac 上的 Command 键来选择多项。留空=不限制。",
    )

    class Meta:
        model = MenuItem
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 动态填充 named_url choices（延迟到此时，避免过早加载 URLConf）
        route_names = discover_named_urls()
        self.fields["named_url"].choices = [("", "——（不使用命名路由）——")] + [(n, n) for n in route_names]

        # 仅允许“无链接”或“分组标题”作为可选父级：即没有 external_url / named_url / flatpage 的项或 is_group_header=True
        if 'parent' in self.fields:
            from django.db.models import Q
            base_qs = MenuItem.objects.filter(
                Q(external_url__isnull=True) | Q(external_url=''),
                Q(named_url__isnull=True) | Q(named_url=''),
                flatpage__isnull=True,
            ) | MenuItem.objects.filter(is_group_header=True)
            allowed = MenuItem.objects.filter(pk__in=base_qs.values('pk'))
            if self.instance and self.instance.pk:
                allowed = allowed.exclude(pk=self.instance.pk)
            parent_field = self.fields.get('parent')
            if parent_field:
                parent_field.queryset = allowed  # type: ignore[attr-defined]

        # 若当前实例的 named_url 不在 choices（路由变化）则补上提示
        cur = (getattr(self.instance, 'named_url', '') or "").strip()
        if cur and all(cur != c[0] for c in self.fields["named_url"].choices):
            self.fields["named_url"].choices = [(cur, f"{cur}（当前值，路由可能已变动）")] + list(self.fields["named_url"].choices)

    # 默认 save 即可，无额外同步逻辑

