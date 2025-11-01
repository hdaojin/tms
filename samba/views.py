from django.shortcuts import render, redirect
from django.contrib import messages


from .forms import SambaPasswordForm
from .samba_sync import enable_samba_for_user, change_samba_password, is_samba_enabled


def samba_account_view(request):
    user = request.user
    enabled = is_samba_enabled(user)

    if request.method == "POST":
        action = request.POST.get("action")
        form = SambaPasswordForm(request.POST, user=user)

        if action not in {"enable", "change"}:
            messages.error(request, "无效的操作。")
            return redirect("samba:samba-account")

        if not form.is_valid():
            # 校验失败，回显表单与当前状态
            return render(request, "samba/samba_account.html", {
                "enabled": enabled,
                "form": form,
            })

        try:
            if action == "enable":
                # 若已开通，再次“enable”等价于确保组并改密
                result = enable_samba_for_user(user, form.password)
                tip = "完成开通" if result["created"] else "已存在，已更新密码与组"
                messages.success(request, f"Samba 账户{tip}。")
                # 开通后刷新状态
                enabled = True
            elif action == "change":
                if not enabled:
                    messages.error(request, "Samba 用户尚未开通，无法修改密码。")
                    return redirect("samba:samba-account")
                change_samba_password(user, form.password)
                messages.success(request, "Samba 密码已修改。")
        except Exception as e:
            messages.error(request, f"操作失败：{e}")

        # 处理完 POST 后回到页面，避免重复提交
        return redirect("samba:samba-account")

    # GET：渲染
    form = SambaPasswordForm(user=user)
    return render(request, "samba/samba_account.html", {
        "enabled": enabled,
        "form": form,
    })