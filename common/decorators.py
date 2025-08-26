# common/decorators.py
"""
自定义装饰器模块
提供一些常用的视图装饰器
"""

from django.contrib.auth.decorators import user_passes_test


# Requires the user to be superuser
superuser_required = user_passes_test(lambda u: u.is_authenticated and u.is_superuser)