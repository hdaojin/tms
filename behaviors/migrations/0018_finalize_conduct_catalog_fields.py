import django.db.models.deletion
from django.db import migrations, models


NATURE_CHOICES = [('REWARD', '奖励'), ('PENALTY', '惩罚')]
STATUS_CHOICES = [
    ('PENDING', '待审核'),
    ('APPROVED', '已通过'),
    ('REJECTED', '已驳回'),
]


class Migration(migrations.Migration):
    dependencies = [('behaviors', '0017_migrate_conduct_catalog_data')]

    operations = [
        migrations.RemoveConstraint(
            model_name='conductseverityrule',
            name='uniq_conduct_severity_rule_nature_severity',
        ),
        migrations.RemoveField(model_name='conductseverityrule', name='severity'),
        migrations.RenameField(
            model_name='conductseverityrule',
            old_name='severity_config',
            new_name='severity',
        ),
        migrations.AlterField(
            model_name='conductseverityrule',
            name='severity',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='rules',
                to='behaviors.conductseverity',
                verbose_name='程度',
            ),
        ),
        migrations.RemoveField(model_name='conductrecord', name='severity'),
        migrations.RenameField(
            model_name='conductrecord',
            old_name='severity_config',
            new_name='severity',
        ),
        migrations.AlterField(
            model_name='conductrecord',
            name='severity',
            field=models.ForeignKey(
                help_text='当前分值 = 事项默认分值 × 严重程度系数',
                on_delete=django.db.models.deletion.PROTECT,
                related_name='records',
                to='behaviors.conductseverity',
                verbose_name='严重程度',
            ),
        ),
        migrations.AlterField(
            model_name='conductcategory',
            name='code',
            field=models.CharField(max_length=64, unique=True, verbose_name='分类代码'),
        ),
        migrations.AlterField(
            model_name='conductitem',
            name='code',
            field=models.CharField(max_length=64, verbose_name='事项代码'),
        ),
        migrations.AlterField(
            model_name='conductcategory',
            name='nature',
            field=models.CharField(
                choices=NATURE_CHOICES,
                help_text='行为性质：奖励、惩罚',
                max_length=20,
                verbose_name='性质',
            ),
        ),
        migrations.AlterField(
            model_name='conductseverityrule',
            name='nature',
            field=models.CharField(choices=NATURE_CHOICES, max_length=20, verbose_name='性质'),
        ),
        migrations.AlterField(
            model_name='conductrecord',
            name='status',
            field=models.CharField(
                choices=STATUS_CHOICES,
                default='PENDING',
                max_length=10,
                verbose_name='状态',
            ),
        ),
        migrations.AddConstraint(
            model_name='conductitem',
            constraint=models.UniqueConstraint(
                fields=('category', 'code'),
                name='uniq_conduct_item_category_code',
            ),
        ),
        migrations.AddConstraint(
            model_name='conductseverityrule',
            constraint=models.UniqueConstraint(
                fields=('nature', 'severity'),
                name='uniq_conduct_severity_rule_nature_severity',
            ),
        ),
        migrations.AddConstraint(
            model_name='conductseverityrule',
            constraint=models.UniqueConstraint(
                condition=models.Q(('is_default', True)),
                fields=('nature',),
                name='uniq_default_conduct_severity_rule_per_nature',
            ),
        ),
        migrations.AddConstraint(
            model_name='conductseverityrule',
            constraint=models.CheckConstraint(
                condition=models.Q(('multiplier__gte', 0)),
                name='conduct_severity_rule_multiplier_nonnegative',
            ),
        ),
    ]
