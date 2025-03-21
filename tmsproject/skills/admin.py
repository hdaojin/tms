from django.contrib import admin
from .models import Module, Topic, Skill, ExamPoint

# 定义ModelAdmin类
class ModuleAdmin(admin.ModelAdmin):
    list_display = ('code', 'name')
    search_fields = ('code', 'name')

class TopicAdmin(admin.ModelAdmin):
    list_display = ('module', 'name')
    search_fields = ('name', 'description')
    list_filter = ('module',)  # 在后台管理页面中添加过滤器
    

class SkillAdmin(admin.ModelAdmin):
    list_display = ('topic', 'name')
    search_fields = ('name', 'description')
    list_filter = ('topic',)  # 在后台管理页面中添加过滤器


class ExamPointAdmin(admin.ModelAdmin):
    # 修改list_display, 用 display_skills 替代原来的 'skill'
    list_display = ('name', 'competition', 'display_skills', 'detail_content', 'difficulty', 'score')
    search_fields = ('name', 'detail_content', 'difficulty')
    list_filter = ('competition', 'skill', 'difficulty')  # 在后台管理页面中添加过滤器
    filter_horizontal = ('skill',)  # 在后台管理页面中使用多选框
    
    # 新增方法，用于显示所属skill的名称列表
    def display_skills(self, obj):
        return ", ".join([skill.name for skill in obj.skill.all()])
    display_skills.short_description = "技能点"

# 按照希望的顺序注册模型
admin.site.register(Module, ModuleAdmin)
admin.site.register(Topic, TopicAdmin)
admin.site.register(Skill, SkillAdmin)
admin.site.register(ExamPoint, ExamPointAdmin)