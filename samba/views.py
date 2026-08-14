from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import permission_required


from .forms import SambaPasswordForm
from .models import SambaOperation
from .services import (
    SambaIntegrationDisabled,
    SambaOperationConflict,
    get_last_known_enabled_state,
    get_latest_operation_for_user,
    submit_operation,
)


@permission_required("samba.add_sambaoperation", raise_exception=True)
def samba_account_view(request):
    user = request.user
    last_known_enabled_state = get_last_known_enabled_state(user)
    enabled = bool(last_known_enabled_state)
    enabled_state_known = last_known_enabled_state is not None
    latest_operation = get_latest_operation_for_user(user)
    # 获取服务器 IP（从请求的 host 中提取，去掉端口号）
    server_host = request.get_host().split(':')[0]

    if request.method == "POST":
        action = request.POST.get("action")
        form = SambaPasswordForm(request.POST, user=user)

        if action not in {"enable", "change"}:
            messages.error(request, "无效的操作。")
            return redirect("samba:accounts")

        if not form.is_valid():
            # 校验失败，回显表单与当前状态
            return render(request, "samba/samba_account.html", {
                "enabled": enabled,
                "form": form,
                "server_host": server_host,
                "title": "Samba 账户管理",
                "title_icon" : "icon-[tabler--users-plus]"
            })

        try:
            if action == "enable":
                submit_operation(
                    actor=request.user,
                    target_user=user,
                    action=SambaOperation.Action.ENABLE,
                    password=form.password,
                )
                messages.success(request, "Samba 开通请求已提交，等待后台队列处理。")
            elif action == "change":
                if not enabled:
                    messages.error(request, "Samba 用户尚未开通，无法修改密码。")
                    return redirect("samba:accounts")
                submit_operation(
                    actor=request.user,
                    target_user=user,
                    action=SambaOperation.Action.CHANGE_PASSWORD,
                    password=form.password,
                )
                messages.success(request, "Samba 改密请求已提交，等待后台队列处理。")
        except (SambaIntegrationDisabled, SambaOperationConflict) as e:
            messages.error(request, str(e))
        except Exception as e:
            messages.error(request, f"操作失败：{e}")

        # 处理完 POST 后回到页面，避免重复提交
        return redirect("samba:accounts")

    # GET：渲染
    form = SambaPasswordForm(user=user)
    return render(request, "samba/samba_account.html", {
        "enabled": enabled,
        "enabled_state_known": enabled_state_known,
        "form": form,
        "latest_operation": latest_operation,
        "server_host": server_host,
        "title": "Samba 账户管理",
        "title_icon" : "icon-[tabler--users-plus]"
    })
