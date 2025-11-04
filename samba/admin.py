from django.contrib import admin
from django.contrib.auth.models import Group
from django.contrib.auth.admin import GroupAdmin as DjangoGroupAdmin
from .models import SambaGroupMap


class SambaGroupMapInline(admin.StackedInline):
    model = SambaGroupMap
    can_delete = False
    fk_name = 'group'
    extra = 0
    fields = ('unix_name',)
    verbose_name = 'Samba 组映射'
    verbose_name_plural = 'Samba 组映射'

class GroupAdmin(DjangoGroupAdmin):
    inlines = (SambaGroupMapInline,)

    def unix_name(self, obj):
        return getattr(getattr(obj, 'samba_group_map', None), 'unix_name', "")
    unix_name.short_description = 'Unix 组名'  # type: ignore[attr-defined]

    list_display = DjangoGroupAdmin.list_display + ('unix_name',) # type: ignore[assignment]

    
admin.site.unregister(Group)
admin.site.register(Group, GroupAdmin)