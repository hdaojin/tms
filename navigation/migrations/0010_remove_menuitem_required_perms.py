from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [
        ('navigation', '0009_menuitem_permissions'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='menuitem',
            name='required_perms',
        ),
    ]
