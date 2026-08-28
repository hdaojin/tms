import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('event_countdown', '0005_migrate_countdown_event_types')]

    operations = [
        migrations.RemoveField(model_name='countdownevent', name='event_type'),
        migrations.RenameField(
            model_name='countdownevent',
            old_name='event_type_config',
            new_name='event_type',
        ),
        migrations.AlterField(
            model_name='countdownevent',
            name='event_type',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='events',
                to='event_countdown.countdowneventtype',
                verbose_name='事件类型',
            ),
        ),
    ]
