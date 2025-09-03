# navigation/signals.py
from django.db.models.signals import post_save, post_delete, m2m_changed
from django.dispatch import receiver
from django.core.cache import cache
from .models import Menu, MenuItem


# 清除菜单项缓存

def bust(menu_ids):
    for mid in menu_ids:
        cache.delete(f"nav.m2m_items.{mid}")

@receiver(post_save, sender=Menu)
@receiver(post_delete, sender=Menu)
def menu_changed(sender, instance, **kwargs):
    bust([instance.id])

@receiver(post_save, sender=MenuItem)
@receiver(post_delete, sender=MenuItem)
def menuitem_changed(sender, instance, **kwargs):
    bust(list(instance.menus.values_list("id", flat=True)))

@receiver(m2m_changed, sender=MenuItem.menus.through)
def menuitem_m2m_changed(sender, instance, action, reverse, model, pk_set, **kwargs):
    if action in {"post_add", "post_remove", "post_clear"}:
        if pk_set:
            bust(pk_set)
        else:
            # post_clear
            bust(list(model.objects.values_list("id", flat=True)))
