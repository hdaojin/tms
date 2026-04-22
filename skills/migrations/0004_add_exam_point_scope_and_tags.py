from decimal import Decimal

import django.db.models.deletion
from django.core.validators import MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('competitions', '0012_alter_competitionproject_document'),
        ('skills', '0003_topic_module_to_competitions_module'),
    ]

    operations = [
        migrations.CreateModel(
            name='TagGroup',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True, verbose_name='名称')),
                ('slug', models.SlugField(max_length=100, unique=True, verbose_name='标识')),
                ('description', models.TextField(blank=True, verbose_name='描述')),
                ('sort_order', models.PositiveIntegerField(default=0, help_text='数值越小越靠前显示。', verbose_name='显示顺序')),
            ],
            options={
                'verbose_name': '标签分组',
                'verbose_name_plural': '标签分组',
                'ordering': ['sort_order', 'name'],
            },
        ),
        migrations.CreateModel(
            name='Tag',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, verbose_name='名称')),
                ('slug', models.SlugField(max_length=100, unique=True, verbose_name='标识')),
                ('description', models.TextField(blank=True, verbose_name='描述')),
                ('sort_order', models.PositiveIntegerField(default=0, help_text='数值越小越靠前显示。', verbose_name='显示顺序')),
                ('is_active', models.BooleanField(default=True, verbose_name='启用')),
                ('group', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tags', to='skills.taggroup', verbose_name='所属分组')),
            ],
            options={
                'verbose_name': '标签',
                'verbose_name_plural': '标签',
                'ordering': ['group', 'sort_order', 'name'],
            },
        ),
        migrations.CreateModel(
            name='ExamPointSkill',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_primary', models.BooleanField(default=False, help_text='用于标识该考点的主要能力点。', verbose_name='主技能')),
                ('weight', models.DecimalField(decimal_places=2, default=Decimal('1.00'), help_text='用于表示该技能点在综合考点中的相对权重。', max_digits=5, validators=[MinValueValidator(Decimal('0.01'))], verbose_name='权重')),
                ('note', models.TextField(blank=True, verbose_name='备注')),
                ('exam_point', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='exam_point_skills', to='skills.exampoint', verbose_name='考点')),
                ('skill', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='exam_point_skills', to='skills.skill', verbose_name='技能点')),
            ],
            options={
                'verbose_name': '考点技能关联',
                'verbose_name_plural': '考点技能关联',
                'ordering': ['exam_point', '-is_primary', 'pk'],
            },
        ),
        migrations.AddConstraint(
            model_name='tag',
            constraint=models.UniqueConstraint(fields=('group', 'name'), name='unique_tag_name_within_group'),
        ),
        migrations.AddConstraint(
            model_name='exampointskill',
            constraint=models.UniqueConstraint(fields=('exam_point', 'skill'), name='unique_exam_point_skill'),
        ),
        migrations.AddField(
            model_name='exampoint',
            name='competition_project',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='exam_points', to='competitions.competitionproject', verbose_name='所属具体赛项'),
        ),
        migrations.AddField(
            model_name='exampoint',
            name='tags',
            field=models.ManyToManyField(blank=True, related_name='exam_points', to='skills.tag', verbose_name='标签'),
        ),
    ]