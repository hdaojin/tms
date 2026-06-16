from django.contrib.auth import get_user_model
from django.db.models.signals import pre_save
from django.dispatch import receiver

from accounts.services.users import fill_leave_date_on_deactivation


User = get_user_model()


@receiver(pre_save, sender=User)
def set_leave_date_when_user_is_deactivated(sender, instance, **kwargs):
    if not instance.pk:
        return

    try:
        previous_is_active = sender.objects.only("is_active").get(pk=instance.pk).is_active
    except sender.DoesNotExist:
        return

    fill_leave_date_on_deactivation(
        instance,
        previous_is_active=previous_is_active,
    )
