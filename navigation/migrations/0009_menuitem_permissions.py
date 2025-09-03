from django.db import migrations, models


def forwards(apps, schema_editor):
    MenuItem = apps.get_model('navigation', 'MenuItem')
    Permission = apps.get_model('auth', 'Permission')
    for item in MenuItem.objects.all():
        if getattr(item, 'required_perms', None):
            codes = [p.split('.') for p in item.required_perms if '.' in p]
            perms = Permission.objects.filter(content_type__app_label__in=[c[0] for c in codes], codename__in=[c[1] for c in codes])
            if perms.exists():
                item.permissions.add(*perms)


def backwards(apps, schema_editor):
    MenuItem = apps.get_model('navigation', 'MenuItem')
    for item in MenuItem.objects.all():
        perms = item.permissions.all()
        item.required_perms = [f"{p.content_type.app_label}.{p.codename}" for p in perms]
        item.save(update_fields=['required_perms'])


class Migration(migrations.Migration):
    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
        ('navigation', '0008_menuitem_is_group_header_alter_menuitem_css_classes_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='menuitem',
            name='permissions',
            field=models.ManyToManyField(blank=True, help_text='留空=不限制；可多选。', related_name='navigation_menu_items', to='auth.permission', verbose_name='所需权限'),
        ),
        migrations.RunPython(forwards, backwards),
    ]
