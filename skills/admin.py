from django.contrib import admin
from .models import ExamPoint, ExamPointSkill, Skill, Tag, TagGroup, Topic

class TopicAdmin(admin.ModelAdmin):
    list_display = ('module', 'name')
    search_fields = ('name', 'description')
    list_filter = ('module',)  # 在后台管理页面中添加过滤器
    list_select_related = ('module',)
    

class SkillAdmin(admin.ModelAdmin):
    list_display = ('topic', 'name')
    search_fields = ('name', 'description')
    list_filter = ('topic',)  # 在后台管理页面中添加过滤器
    list_select_related = ('topic', 'topic__module')


class TagGroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'sort_order')
    search_fields = ('name', 'slug', 'description')
    ordering = ('sort_order', 'name')


class TagAdmin(admin.ModelAdmin):
    list_display = ('name', 'group', 'slug', 'is_active', 'sort_order')
    list_filter = ('group', 'is_active')
    search_fields = ('name', 'slug', 'description')
    autocomplete_fields = ['group']
    list_select_related = ('group',)
    ordering = ('group__sort_order', 'group__name', 'sort_order', 'name')


class ExamPointSkillInline(admin.TabularInline):
    model = ExamPointSkill
    extra = 0
    autocomplete_fields = ['skill']
    fields = ('skill', 'is_primary', 'weight', 'note')


class ExamPointAdmin(admin.ModelAdmin):
    list_display = ('name', 'competition_project', 'display_skills', 'display_tags', 'difficulty', 'score')
    search_fields = (
        'name',
        'detail_content',
        'competition_project__competition__name',
        'competition_project__project__name',
    )
    list_filter = ('competition_project__competition', 'competition_project__project', 'difficulty', 'tags')
    autocomplete_fields = ['competition_project', 'tags']
    inlines = [ExamPointSkillInline]

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related('competition_project__competition', 'competition_project__project')
            .prefetch_related('exam_point_skills__skill', 'tags')
        )

    @admin.display(description="技能点")
    def display_skills(self, obj):
        skill_labels = []
        for relation in obj.exam_point_skills.all():
            label = relation.skill.name
            if relation.is_primary:
                label = f'★ {label}'
            skill_labels.append(label)
        return ", ".join(skill_labels) or '-'

    @admin.display(description="标签")
    def display_tags(self, obj):
        return ", ".join(tag.name for tag in obj.tags.all()) or '-'

# 按照希望的顺序注册模型
admin.site.register(Topic, TopicAdmin)
admin.site.register(Skill, SkillAdmin)
admin.site.register(TagGroup, TagGroupAdmin)
admin.site.register(Tag, TagAdmin)
admin.site.register(ExamPoint, ExamPointAdmin)