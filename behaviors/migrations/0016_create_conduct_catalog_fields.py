import django.db.models.deletion
from django.db import migrations, models


SEVERITY_CHOICES = [
    ('MINOR', '轻微'),
    ('MODERATE', '一般'),
    ('SEVERE', '严重'),
    ('CRITICAL', '特别严重'),
]


class Migration(migrations.Migration):
    dependencies = [('behaviors', '0015_alter_conductrecord_attachment')]

    operations = [
        migrations.AlterField(
            model_name='conductseverityrule',
            name='severity',
            field=models.CharField(
                choices=SEVERITY_CHOICES,
                max_length=20,
                null=True,
                verbose_name='程度',
            ),
        ),
        migrations.AlterField(
            model_name='conductrecord',
            name='severity',
            field=models.CharField(
                choices=SEVERITY_CHOICES,
                default='MODERATE',
                max_length=20,
                null=True,
                verbose_name='严重程度',
            ),
        ),
        migrations.CreateModel(
            name='ConductSeverity',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=20, unique=True, verbose_name='程度代码')),
                ('name', models.CharField(max_length=50, verbose_name='程度名称')),
                ('description', models.TextField(blank=True, verbose_name='说明')),
                ('is_active', models.BooleanField(default=True, verbose_name='启用状态')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
            ],
            options={
                'verbose_name': '奖惩严重程度',
                'verbose_name_plural': '奖惩严重程度',
                'ordering': ['code'],
            },
        ),
        migrations.AddField(
            model_name='conductcategory',
            name='code',
            field=models.CharField(max_length=64, null=True, verbose_name='分类代码'),
        ),
        migrations.AddField(
            model_name='conductitem',
            name='code',
            field=models.CharField(max_length=64, null=True, verbose_name='事项代码'),
        ),
        migrations.AddField(
            model_name='conductseverityrule',
            name='label',
            field=models.CharField(default='', max_length=50, verbose_name='显示名称'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='conductseverityrule',
            name='is_default',
            field=models.BooleanField(default=False, verbose_name='默认程度'),
        ),
        migrations.AddField(
            model_name='conductseverityrule',
            name='severity_config',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='+',
                to='behaviors.conductseverity',
                verbose_name='程度配置',
            ),
        ),
        migrations.AddField(
            model_name='conductrecord',
            name='severity_config',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='+',
                to='behaviors.conductseverity',
                verbose_name='严重程度配置',
            ),
        ),
    ]
