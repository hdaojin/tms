from django.contrib import admin
from .models import Module, Topic, Skill, ExamPoint

# 定义ModelAdmin类
class ModuleAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'description')
    search_fields = ('code', 'name')

class TopicAdmin(admin.ModelAdmin):
    list_display = ('name', 'description', 'module')
    search_fields = ('name', 'description')

class SkillAdmin(admin.ModelAdmin):
    list_display = ('name', 'description', 'topic')
    search_fields = ('name', 'description')


class ExamPointAdmin(admin.ModelAdmin):
    list_display = ('skill', 'name', 'score')
    search_fields = ('name', 'detail_content')

# 按照希望的顺序注册模型
admin.site.register(Module, ModuleAdmin)
admin.site.register(Topic, TopicAdmin)
admin.site.register(Skill, SkillAdmin)
admin.site.register(ExamPoint, ExamPointAdmin)