# common/mixins.py
"""
自定义类视图混入模块
提供一些常用的类视图混入
"""

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin

class SuperuserRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """
    仅允许超级用户访问的混入
    用法:
        class MyView(SuperuserRequiredMixin, View):
            ...
    """
    raise_exception = True  # If True, raise PermissionDenied on failure, else redirect to login
    def test_func(self):
        return self.request.user.is_superuser # type: ignore