import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('behaviors', '0023_merge_conduct_data')]

    operations = [
        migrations.RemoveField(
            model_name='conductcycleassignment',
            name='can_manage_catalog',
        ),
        migrations.RemoveField(
            model_name='conductpolicyrule',
            name='item',
        ),
        migrations.RemoveField(
            model_name='conductpolicyrule',
            name='points',
        ),
        migrations.RemoveField(
            model_name='conductpolicyrule',
            name='policy',
        ),
        migrations.AlterField(
            model_name='conductpolicyrule',
            name='multiplier',
            field=models.DecimalField(decimal_places=2, max_digits=8, verbose_name='倍率'),
        ),
        migrations.AlterField(
            model_name='conductrecord',
            name='category_label',
            field=models.CharField(editable=False, max_length=100, verbose_name='记录时分类名称'),
        ),
        migrations.AlterField(
            model_name='conductrecord',
            name='item_label',
            field=models.CharField(editable=False, max_length=255, verbose_name='记录时事项名称'),
        ),
        migrations.AlterField(
            model_name='conductrecord',
            name='frozen_points',
            field=models.DecimalField(decimal_places=4, editable=False, max_digits=16, verbose_name='实际积分'),
        ),
        migrations.AddConstraint(
            model_name='conductcategory',
            constraint=models.UniqueConstraint(fields=('nature', 'name'), name='uniq_conduct_category_nature_name'),
        ),
        migrations.AlterField(
            model_name='conductpolicyrule',
            name='policy_item',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='rules', to='behaviors.conductpolicyitem', verbose_name='条例事项'),
        ),
        migrations.RemoveField(
            model_name='conductcategory',
            name='cycle',
        ),
        migrations.DeleteModel(
            name='CycleConductRecord',
        ),
    ]
