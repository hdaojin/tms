import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('event_countdown', '0003_alter_countdownevent_theme')]

    operations = [
        migrations.AlterField(
            model_name='countdownevent',
            name='event_type',
            field=models.CharField(
                choices=[
                    ('worldskills', '世界技能大赛'),
                    ('national', '全国技能大赛'),
                    ('provincial', '省级技能大赛'),
                    ('municipal', '市级技能大赛'),
                    ('school', '校内比赛'),
                    ('training', '集训活动'),
                    ('exam', '考核测评'),
                    ('meeting', '会议活动'),
                    ('other', '其他活动'),
                ],
                default='other',
                max_length=20,
                null=True,
                verbose_name='事件类型',
            ),
        ),
        migrations.CreateModel(
            name='CountdownEventType',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=20, unique=True, verbose_name='类型代码')),
                ('name', models.CharField(max_length=120, verbose_name='类型名称')),
                ('description', models.TextField(blank=True, verbose_name='说明')),
                ('order', models.PositiveIntegerField(default=0, verbose_name='排序')),
                ('is_active', models.BooleanField(default=True, verbose_name='启用')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
            ],
            options={
                'verbose_name': '倒计时事件类型',
                'verbose_name_plural': '倒计时事件类型',
                'ordering': ['order', 'code'],
            },
        ),
        migrations.AddField(
            model_name='countdownevent',
            name='event_type_config',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='+',
                to='event_countdown.countdowneventtype',
                verbose_name='事件类型配置',
            ),
        ),
    ]
