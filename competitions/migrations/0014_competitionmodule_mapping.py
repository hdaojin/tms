from decimal import Decimal

import django.db.models.deletion
from django.core.validators import MinValueValidator
from django.db import migrations, models


def populate_competition_modules(apps, schema_editor):
    CompetitionModule = apps.get_model('competitions', 'CompetitionModule')
    CompetitionModuleMapping = apps.get_model('competitions', 'CompetitionModuleMapping')

    db_alias = schema_editor.connection.alias
    competition_modules = CompetitionModule.objects.using(db_alias).select_related('module').order_by(
        'competition_project_id',
        'module__sort_order',
        'module__code',
        'pk',
    )

    for competition_module in competition_modules:
        module = competition_module.module
        updates = []
        if not competition_module.code:
            competition_module.code = module.code
            updates.append('code')
        if not competition_module.name:
            competition_module.name = module.name
            updates.append('name')
        if not competition_module.description:
            competition_module.description = module.description
            updates.append('description')
        if competition_module.sort_order == 0:
            competition_module.sort_order = module.sort_order
            updates.append('sort_order')
        if updates:
            competition_module.save(update_fields=updates)

        CompetitionModuleMapping.objects.using(db_alias).get_or_create(
            competition_module_id=competition_module.pk,
            module_id=module.pk,
            defaults={
                'is_primary': True,
                'weight': Decimal('1.00'),
                'note': '',
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ('competitions', '0013_moduleset_versioning'),
    ]

    operations = [
        migrations.CreateModel(
            name='CompetitionModuleMapping',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_primary', models.BooleanField(default=False, help_text='用于标识该官方模块当前主要对应的标准模块。', verbose_name='主映射')),
                ('weight', models.DecimalField(decimal_places=2, default=Decimal('1.00'), help_text='用于表示该官方模块映射到该标准模块时的相对权重。', max_digits=5, validators=[MinValueValidator(Decimal('0.01'))], verbose_name='权重')),
                ('note', models.TextField(blank=True, verbose_name='备注')),
                ('competition_module', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='module_mappings', to='competitions.competitionmodule', verbose_name='具体赛项模块')),
                ('module', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='competition_module_mappings', to='competitions.module', verbose_name='标准模块')),
            ],
            options={
                'verbose_name': '赛项模块映射',
                'verbose_name_plural': '赛项模块映射',
                'ordering': ['competition_module', '-is_primary', 'module__sort_order', 'module__code', 'pk'],
                'unique_together': {('competition_module', 'module')},
            },
        ),
        migrations.AddField(
            model_name='competitionmodule',
            name='code',
            field=models.CharField(blank=True, help_text='按该届官方模块原始编号填写；如留空且已选择主标准模块，将自动回填。', max_length=50, verbose_name='本届模块编号'),
        ),
        migrations.AddField(
            model_name='competitionmodule',
            name='description',
            field=models.TextField(blank=True, verbose_name='本届模块描述'),
        ),
        migrations.AddField(
            model_name='competitionmodule',
            name='sort_order',
            field=models.PositiveIntegerField(default=0, help_text='数值越小越靠前显示。', verbose_name='显示顺序'),
        ),
        migrations.AlterModelOptions(
            name='competitionmodule',
            options={
                'verbose_name': '具体赛项模块',
                'verbose_name_plural': '具体赛项模块',
                'ordering': ['competition_project', 'sort_order', 'code', 'pk'],
            },
        ),
        migrations.AlterField(
            model_name='competitionmodule',
            name='module',
            field=models.ForeignKey(blank=True, help_text='过渡期兼容字段，用于指向该官方模块当前的主标准模块映射。', null=True, on_delete=django.db.models.deletion.PROTECT, related_name='competition_modules', to='competitions.module', verbose_name='主标准模块'),
        ),
        migrations.AlterField(
            model_name='competitionmodule',
            name='name',
            field=models.CharField(blank=True, help_text='如不填则优先使用主标准模块名称自动回填。', max_length=100, verbose_name='本届模块名称'),
        ),
        migrations.RunPython(populate_competition_modules, migrations.RunPython.noop),
        migrations.AlterUniqueTogether(
            name='competitionmodule',
            unique_together={('competition_project', 'code')},
        ),
    ]