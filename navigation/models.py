# navigation/models.py
from django.db import models
from django.core.exceptions import ValidationError
from multiselectfield import MultiSelectField
from django.contrib.auth.models import Permission

# 菜单组
class Menu(models.Model):
    slug = models.SlugField("菜单组标识", max_length=50, unique=True,
                            help_text="用于标识菜单的唯一标识符，如 'main', 'user', 'meeting' 等")
    name = models.CharField("菜单组名称", max_length=100, help_text="菜单的显示名称")
    description = models.TextField("菜单组描述", blank=True, help_text="对菜单的简要描述")

    class Location(models.TextChoices):
        MAIN = 'header', '顶部菜单'
        SIDEBAR = 'sidebar', '侧边栏菜单'
        FOLLOW = 'follow', '跟随应用'
        FOOTER = 'footer', '页脚菜单'
        CUSTOM = 'custom', '自定义位置'

    locations = MultiSelectField("显示位置", choices=Location, max_length=200,
                                 default=Location.MAIN, help_text="菜单显示的位置，可多选")
    is_active = models.BooleanField("启用", default=True, help_text="是否启用此菜单")

    class Meta:
        verbose_name = "菜单组"
        verbose_name_plural = "菜单组"

    def __str__(self):
        return f"{self.name}({self.slug})"

# 菜单项
class MenuItem(models.Model):
    menus = models.ManyToManyField(Menu, related_name='items', verbose_name="所属菜单组",
                                   help_text="此菜单项可以同时属于多个菜单组")
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True,
                               related_name='children', verbose_name="上级菜单项")

    name = models.CharField("菜单项名称", max_length=100, help_text="菜单项的显示名称")
    icon = models.CharField("图标", max_length=100, blank=True,
                            help_text="菜单项的图标类名，如 icon-[tabler--home], 图标类名参考https://icon-sets.iconify.design/tabler/")
    order = models.PositiveIntegerField("排序", default=0, help_text="菜单项的显示顺序，数字越小越靠前")

    # 显示控制
    is_visible = models.BooleanField("可见", default=True, help_text="是否在菜单中显示此项")
    start_at = models.DateTimeField("开始时间", null=True, blank=True,
                                    help_text="菜单项显示的开始时间，留空表示立即开始")
    end_at = models.DateTimeField("结束时间", null=True, blank=True,
                                  help_text="菜单项显示的结束时间，留空表示无限期")

    # 权限控制：直接关联内置 Permission
    permissions = models.ManyToManyField(
        Permission,
        related_name="navigation_menu_items",
        blank=True,
        verbose_name="所需权限",
        help_text="留空=不限制；可多选。"
    )
    perm_match_all = models.BooleanField("权限需全部满足", default=True,
                                         help_text="选中=需满足全部；未选中=满足任一即可")
    login_required = models.BooleanField("登录可见", default=True, help_text="仅对已登录用户显示此菜单项")

    # 是否分组标题（无链接，仅作为折叠/分组用）
    is_group_header = models.BooleanField("仅分组标题（无链接）", default=False)

    # 指向方式
    named_url = models.CharField("命名路由", max_length=200, blank=True,
                                 help_text="从已发现的命名URL列表中选择；留空表示不使用命名路由")
    url_kwargs = models.JSONField("路由参数", default=dict, blank=True,
                                  help_text='命名路由的参数，如 {"pk": 1}')
    url_query = models.JSONField("路由查询参数", default=dict, blank=True,
                                 help_text='例如 {"tab": "files"}')
    flatpage = models.ForeignKey('flatpages.FlatPage', on_delete=models.SET_NULL,
                                 null=True, blank=True, verbose_name="简单页面",
                                 help_text="选择一个简单页面")
    external_url = models.URLField("外部链接", max_length=500, blank=True,
                                   help_text="外部链接地址，如 'https://example.com'")

    # 其他前端属性
    target_blank = models.BooleanField("新标签页打开", default=False)
    css_classes = models.CharField("CSS类", max_length=200, blank=True,
                                   help_text='如 "text-primary font-bold"')
    htmx_attrs = models.JSONField("HTMX属性", default=dict, blank=True,
                                  help_text='如 {"hx-get": "/some/url/"}')

    class Meta:
        ordering = ['parent__id', 'order', 'id']
        verbose_name = "菜单项"
        verbose_name_plural = "菜单项"
        indexes = [
            models.Index(fields=['parent', 'order', 'id']),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        # 分组标题无链接；非分组最多允许一种链接
        link_fields = [bool(self.external_url), bool(self.named_url), bool(self.flatpage)]  
        link_count = sum(link_fields)
        if self.is_group_header:
            if link_count > 0:
                raise ValidationError("分组标题不应配置任何链接。")
        else:
            if link_count > 1:
                raise ValidationError("命名路由 / FlatPage / 外部链接 只能选择一种。")

        # 父级限制：父级必须是“无链接”或分组标题
        if self.parent_id:  # type: ignore
            p = self.parent  # type: ignore
            parent_has_link = any([p.external_url, p.named_url, p.flatpage_id])  # type: ignore
            if parent_has_link and not p.is_group_header:  # type: ignore
                raise ValidationError("父级菜单必须是【无链接】或勾选为分组标题的菜单项。")
