from django.contrib import admin
from .models import Notice, NoticeAttachment
from django.utils import timezone

# Register your models here.

class NoticeAttachmentInline(admin.TabularInline):
    """
    通知附件内联编辑
    """
    model = NoticeAttachment
    extra = 1
    fields = ('file', 'file_name', 'file_size_human', 'uploaded_at')
    readonly_fields = ('file_name', 'file_size_human', 'uploaded_at')
    
    @admin.display(description='文件名')
    def file_name(self, obj):
        return obj.file_name if obj else ''
    
    @admin.display(description='文件大小')
    def file_size_human(self, obj):
        return obj.file_size_human if obj else ''

class NoticeAdmin(admin.ModelAdmin):
    list_display = ('title', 'content', 'get_attachments_count', 'is_published', 'published_by', 'get_target_groups_display', 'published_at', 'updated_at')
    list_filter = ('is_published', 'published_by', 'target_groups')
    search_fields = ('title', 'content')
    readonly_fields = ('published_at', 'updated_at')
    date_hierarchy = 'published_at'
    ordering = ('-is_published', '-published_at', '-updated_at')
    actions = ['publish_notices', 'unpublish_notices']
    filter_horizontal = ('target_groups',)  # 使用水平过滤器选择组
    inlines = [NoticeAttachmentInline]  # 添加附件内联编辑

    @admin.display(description='附件数量')
    def get_attachments_count(self, obj):
        """显示附件数量"""
        count = obj.attachments.count()
        return f"{count} 个附件" if count > 0 else "无附件"

    @admin.display(description='目标组')
    def get_target_groups_display(self, obj):
        """显示目标组"""
        if obj.target_groups.exists():
            return ', '.join([group.name for group in obj.target_groups.all()])
        return '所有用户'

    def get_fields(self, request, obj=None):
        """根据用户权限动态调整字段显示"""
        fields = ['title', 'content', 'target_groups', 'is_published']
        
        # 只有超级用户才能看到和编辑发布人字段
        if request.user.is_superuser:
            fields.append('published_by')
        
        fields.extend(['published_at', 'updated_at'])
        return fields

    def get_readonly_fields(self, request, obj=None):
        """根据用户权限动态调整只读字段"""
        readonly_fields = ['published_at', 'updated_at']
        
        # 对于非超级用户，如果显示发布人字段则设为只读
        if not request.user.is_superuser and 'published_by' in self.get_fields(request, obj):
            readonly_fields.append('published_by')
            
        return readonly_fields

    def save_model(self, request, obj, form, change):
        """保存时自动设置发布人和发布时间"""
        # 如果通知被设置为发布状态
        if obj.is_published:
            # 如果是新创建的对象或者发布人为空，设置为当前用户
            if not change or not obj.published_by:
                obj.published_by = request.user
            
            # 如果发布时间为空，设置为当前时间
            if not obj.published_at:
                obj.published_at = timezone.now()
            
            # 如果不是超级用户，强制设置发布人为当前用户
            if not request.user.is_superuser:
                obj.published_by = request.user
        else:
            # 如果取消发布，清除发布时间和发布人
            obj.published_at = None
            obj.published_by = None
            
        super().save_model(request, obj, form, change)

    @admin.action(description='发布选中通知')
    def publish_notices(self, request, queryset):
        queryset.update(is_published=True, published_by=request.user, published_at=timezone.now())
        self.message_user(request, f"已发布 {queryset.count()} 条通知。")

    @admin.action(description='撤销选中通知')
    def unpublish_notices(self, request, queryset):
        queryset.update(is_published=False, published_by=None, published_at=None)
        self.message_user(request, f"已撤销 {queryset.count()} 条通知。")
    

# 注册模型和自定义的Admin类
admin.site.register(Notice, NoticeAdmin)
admin.site.register(NoticeAttachment)