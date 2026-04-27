from django.db import migrations, models


class Migration(migrations.Migration):

	dependencies = [
		('competitions', '0026_competitionprojectmember'),
	]

	operations = [
		migrations.AddConstraint(
			model_name='competitor',
			constraint=models.UniqueConstraint(
				fields=('competition_project', 'person'),
				name='unique_competitor_per_competition_project',
			),
		),
	]