from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'
    verbose_name = "用户管理"
    verbose_name_plural = "用户管理"
    
    def ready(self):
        """应用启动时自动执行，给 User 模型添加属性"""
        from django.contrib.auth import get_user_model
        
        User = get_user_model()
        
        # 如果已经有这个属性了，跳过（防止重复添加）
        if not hasattr(User, 'display_name'):
            @property
            def display_name(self):
                """
                用户显示名称
                组合 last_name（姓）+ first_name（名），无则使用 username
                """
                full_name = f"{self.last_name}{self.first_name}".strip()
                return full_name or self.username
            
            User.display_name = display_name    # type: ignore
        
        if not hasattr(User, 'full_info'):
            @property
            def full_info(self):
                """
                用户完整信息: 姓名(用户名)
                如: 张三(student001)
                """
                full_name = f"{self.last_name}{self.first_name}".strip()
                name = full_name or self.username
                if self.first_name and self.username:
                    return f"{name}({self.username})"
                return name
            
            User.full_info = full_info    # type: ignore
        



    
