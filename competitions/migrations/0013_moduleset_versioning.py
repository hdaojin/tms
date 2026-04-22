from django.db import migrations, models
import django.db.models.deletion


DEFAULT_MODULE_SET_CODE = 'default'
DEFAULT_MODULE_SET_NAME = '默认标准模块集'
DEFAULT_MODULE_SET_DESCRIPTION = '系统自动创建的默认标准模块集。'


def assign_default_module_sets(apps, schema_editor):
    Project = apps.get_model('competitions', 'Project')
    Module = apps.get_model('competitions', 'Module')
    ModuleSet = apps.get_model('competitions', 'ModuleSet')

    db_alias = schema_editor.connection.alias

    for project in Project.objects.using(db_alias).all().iterator():
        module_set = ModuleSet.objects.using(db_alias).create(
            project_id=project.pk,
            code=DEFAULT_MODULE_SET_CODE,
            name=DEFAULT_MODULE_SET_NAME,
            description=DEFAULT_MODULE_SET_DESCRIPTION,
            sort_order=0,
            is_current=True,
        )
        Module.objects.using(db_alias).filter(project_id=project.pk).update(module_set_id=module_set.pk)


def remove_default_module_sets(apps, schema_editor):
    ModuleSet = apps.get_model('competitions', 'ModuleSet')
    db_alias = schema_editor.connection.alias
    ModuleSet.objects.using(db_alias).filter(code=DEFAULT_MODULE_SET_CODE).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('competitions', '0012_alter_competitionproject_document'),
    ]

    operations = [
        migrations.CreateModel(
            name='ModuleSet',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(help_text='同一项目下唯一，用于标识某一版标准模块集。', max_length=50, verbose_name='模块集代码')),
                ('name', models.CharField(help_text='例如：2025 版标准模块、2026 版标准模块。', max_length=100, verbose_name='模块集名称')),
                ('description', models.TextField(blank=True, verbose_name='描述')),
                ('sort_order', models.PositiveIntegerField(default=0, help_text='数值越小越靠前显示。', verbose_name='显示顺序')),
                ('is_current', models.BooleanField(default=False, help_text='同一项目同一时刻只允许一套当前启用的标准模块集。', verbose_name='当前启用')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='最后更新时间')),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='module_sets', to='competitions.project', verbose_name='所属竞赛项目')),
            ],
            options={
                'verbose_name': '标准模块集',
                'verbose_name_plural': '标准模块集',
                'ordering': ['project', '-is_current', 'sort_order', 'name'],
            },
        ),
        migrations.AddField(
            model_name='module',
            name='module_set',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='modules', to='competitions.moduleset', verbose_name='所属标准模块集'),
        ),
        migrations.AddField(
            model_name='module',
            name='sort_order',
            field=models.PositiveIntegerField(default=0, help_text='数值越小越靠前显示。', verbose_name='显示顺序'),
        ),
        migrations.RunPython(assign_default_module_sets, remove_default_module_sets),
        migrations.AlterModelOptions(
            name='module',
            options={
                'verbose_name': '竞赛模块',
                'verbose_name_plural': '竞赛模块',
                'ordering': ['project', 'module_set__sort_order', 'sort_order', 'code', 'name'],
            },
        ),
        migrations.AlterField(
            model_name='module',
            name='module_set',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='modules', to='competitions.moduleset', verbose_name='所属标准模块集'),
        ),
        migrations.AlterUniqueTogether(
            name='module',
            unique_together={('module_set', 'code')},
        ),
        migrations.AddConstraint(
            model_name='moduleset',
            constraint=models.UniqueConstraint(fields=('project', 'code'), name='unique_module_set_code_within_project'),
        ),
        migrations.AddConstraint(
            model_name='moduleset',
            constraint=models.UniqueConstraint(condition=models.Q(is_current=True), fields=('project',), name='unique_current_module_set_per_project'),
        ),
    ]