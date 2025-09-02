from django.db import models
from multiselectfield import MultiSelectField


class Menu(models.Model):
    """
    菜单命名，如 "main"（主菜单），"user"（用户菜单）， "meeting"（会议菜单）等。
    """
    slug = models.SlugField("菜单组标识", max_length=50, unique=True, help_text="用于标识菜单的唯一标识符，如 'main', 'user', 'meeting' 等")
    name = models.CharField("菜单组名称", max_length=100, help_text="菜单的显示名称")
    description = models.TextField("菜单组描述", blank=True, help_text="对菜单的简要描述")

    # 在模板中的位置绑定（可多选）
    class Location(models.TextChoices):
        MAIN = 'header', '顶部菜单'
        USER = 'user', '用户菜单'
        SIDEBAR = 'sidebar', '侧边栏菜单'
        FOOTER = 'footer', '页脚菜单'
        CUSTOM = 'custom', '自定义位置'
    # locations = models.JSONField("显示位置", default=list, help_text="菜单显示的位置，可多选", blank=True) # 存储为列表['main', 'user']
    locations = MultiSelectField("显示位置", choices=Location, max_length=200, default=Location.MAIN, help_text="菜单显示的位置，可多选")
    # 是否启用
    is_active = models.BooleanField("启用", default=True, help_text="是否启用此菜单")

    class Meta:
        verbose_name = "菜单组"
        verbose_name_plural = "菜单组"

    def __str__(self):
        return f"{self.name}({self.slug})"
    

class MenuItem(models.Model):
    """
    树形菜单项。一个菜单项可以有多个子菜单项。
    支持三种类型的链接：
    1. 外部链接（如： 'https://example.com'）
    2. 命名路由（如： 'home', 'meeting:list'）
    3. flatpage 页面（如： FlatPage 实例）
    """

    menus = models.ManyToManyField(Menu, related_name='items', verbose_name="所属菜单组", help_text="此菜单项可以同时属于多个菜单组")
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children', verbose_name="上级菜单项")
    name = models.CharField("菜单项名称", max_length=100, help_text="菜单项的显示名称")
    icon = models.CharField("图标", max_length=100, blank=True, help_text="菜单项的图标类名，如 'icon-[tabler--home]'")
    order = models.PositiveIntegerField("排序", default=0, help_text="菜单项的显示顺序，数字越小越靠前")
    # 显示控制
    is_visible = models.BooleanField("可见", default=True, help_text="是否在菜单中显示此项")
    start_at = models.DateTimeField("开始时间", null=True, blank=True, help_text="菜单项显示的开始时间，留空表示立即开始")
    end_at = models.DateTimeField("结束时间", null=True, blank=True, help_text="菜单项显示的结束时间，留空表示无限期")
    # 权限控制
    required_perms = models.JSONField("所需权限", default=list, blank=True, help_text='访问此菜单项所需的权限列表。支持特殊权限："is_authenticated"(已登录)、"is_staff"(管理员)、"is_superuser"(超级用户)，以及标准权限如"app_label.permission_codename"。例：["is_authenticated", "meeting.view_meeting"]表示需要登录且有查看会议权限的用户才能访问此菜单项，留空表示不限制')
    # 指向方式1：命名路由
    named_url = models.CharField("命名路由", max_length=200, blank=True, help_text="Django 命名路由名称，如 'home', 'meeting:list' 等")
    url_kwargs = models.JSONField("路由参数", default=dict, blank=True, help_text="命名路由的参数，如 {'pk': 1}，留空表示无参数")
    url_query = models.JSONField("路由查询参数", default=dict, blank=True, help_text="命名路由的查询参数，如 {'tab': 'files'}，留空表示无查询参数")
    # 指向方式2：FlatPage 页面
    flatpage = models.ForeignKey('flatpages.FlatPage', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="FlatPage 页面", help_text="选择一个 FlatPage 页面")
    # 指向方式3：外部链接
    external_url = models.URLField("外部链接", max_length=500, blank=True, help_text="外部链接地址，如 'https://example.com'")

    # 其他前端属性
    target_blank = models.BooleanField("新标签页打开", default=False, help_text="是否在新标签页中打开链接")
    css_classes = models.CharField("CSS类", max_length=200, blank=True, help_text="菜单项的自定义CSS类名，如 'text-primary font-bold'")
    htmx_attrs = models.JSONField("HTMX属性", default=dict, blank=True, help_text="菜单项的HTMX属性，如 {'hx-get': '/some/url/'}，留空表示无HTMX属性")

    class Meta:
        ordering = ['parent__id', 'order', 'id']
        verbose_name = "菜单项"
        verbose_name_plural = "菜单项"

    def __str__(self):
        return f"{self.name}"
    




    