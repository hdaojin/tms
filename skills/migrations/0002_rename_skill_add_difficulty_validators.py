from django.core import validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('skills', '0001_initial'),
    ]

    operations = [
        migrations.RenameField(
            model_name='exampoint',
            old_name='skill',
            new_name='skills',
        ),
        migrations.AlterField(
            model_name='exampoint',
            name='difficulty',
            field=models.PositiveSmallIntegerField(
                default=3,
                help_text='1-5，1 最简单，5 最难',
                validators=[validators.MinValueValidator(1), validators.MaxValueValidator(5)],
                verbose_name='难度系数',
            ),
        ),
        migrations.AlterField(
            model_name='exampoint',
            name='name',
            field=models.CharField(
                help_text='必填；同一竞赛下名称唯一。',
                max_length=500,
                verbose_name='考点',
            ),
        ),
    ]