from django.db import migrations, models


class Migration(migrations.Migration):

	dependencies = [
		('competitions', '0016_remove_competitionmodule_module_and_more'),
	]

	operations = [
		migrations.AddField(
			model_name='member',
			name='level',
			field=models.CharField(
				choices=[
					('international', '国家或地区'),
					('national', '省级代表队'),
					('provincial', '地市代表队'),
					('municipal', '区县代表队'),
					('district', '学校代表队'),
					('school', '班级代表队'),
					('class', '班级小组'),
					('other', '其他'),
				],
				default='other',
				help_text='用于匹配赛事级别；国际级赛事应选择“国家或地区”，国家级赛事应选择“省级代表队”，以此类推。',
				max_length=20,
				verbose_name='代表队层级',
			),
			preserve_default=False,
		),
		migrations.AlterModelOptions(
			name='member',
			options={
				'ordering': ['level', 'name'],
				'verbose_name': '参赛代表队',
				'verbose_name_plural': '参赛代表队',
			},
		),
	]