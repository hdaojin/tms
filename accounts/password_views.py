from django.conf import settings
from django.contrib.auth import get_user_model, update_session_auth_hash
from django.contrib.auth.decorators import login_not_required
from django.contrib.auth.views import PasswordChangeDoneView, PasswordChangeView
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.debug import sensitive_post_parameters, sensitive_variables
from django.views.decorators.http import require_http_methods, require_POST

from accounts.forms import PasswordResetLinkIssueForm, StyledPasswordChangeForm, StyledSetPasswordForm
from accounts.services.password_reset import (
    can_issue_password_reset,
    change_own_password,
    consume_password_reset_grant,
    issue_password_reset_grant,
    password_reset_form,
)
from core.utils.mixins import TitleMixin

User = get_user_model()


class AccountPasswordChangeView(TitleMixin, PasswordChangeView):
    title = "修改密码"
    title_icon = "icon-[tabler--lock]"
    template_name = "accounts/password_change.html"
    form_class = StyledPasswordChangeForm
    success_url = reverse_lazy("accounts:password_change_done")

    @sensitive_variables()
    def post(self, request, *args, **kwargs):
        form = change_own_password(user_id=request.user.pk, data=request.POST)
        if not form.is_valid():
            return self.form_invalid(form)
        update_session_auth_hash(request, form.user)
        return redirect(self.get_success_url())


class AccountPasswordChangeDoneView(TitleMixin, PasswordChangeDoneView):
    title = "密码已修改"
    title_icon = "icon-[tabler--lock]"
    template_name = "accounts/password_change_done.html"


def _private_render(request, template, context, *, status=200, referrer_policy="no-referrer"):
    response = render(request, template, context, status=status)
    response["Referrer-Policy"] = referrer_policy
    response["Pragma"] = "no-cache"
    response["X-Robots-Tag"] = "noindex, nofollow"
    return response


@require_POST
@csrf_protect
@never_cache
@sensitive_variables()
def admin_password_reset_issue(request, pk):
    if not request.user.is_active or not request.user.is_superuser:
        raise PermissionDenied
    if not settings.DEBUG and not request.is_secure():
        raise PermissionDenied("请通过 HTTPS 生成密码重置链接。")
    target = get_object_or_404(User, pk=pk)
    if not can_issue_password_reset(request.user, target):
        raise PermissionDenied
    request.get_host()
    form = PasswordResetLinkIssueForm(request.POST)
    context = {"target_user": target, "title": "生成密码重置链接"}
    if not form.is_valid():
        return _private_render(
            request, "accounts/password_reset_link.html", {**context, "issue_form": form}, status=400,
        )
    grant, raw_token = issue_password_reset_grant(
        actor=request.user, target_user_id=pk, **form.cleaned_data,
    )
    path = reverse("accounts:password_reset_grant", kwargs={"grant_id": grant.pk})
    context["reset_link"] = f"{request.build_absolute_uri(path)}#{raw_token}"
    return _private_render(request, "accounts/password_reset_link.html", context)


@login_not_required
@require_http_methods(["GET", "POST"])
@csrf_protect
@never_cache
@sensitive_post_parameters("token", "new_password1", "new_password2")
@sensitive_variables()
def password_reset_grant(request, grant_id):
    if not settings.DEBUG and not request.is_secure():
        raise PermissionDenied("请通过 HTTPS 打开密码重置链接。")
    context = {"title": "重置密码"}
    if request.method == "POST":
        token = request.POST.get("token", "")
        data = {name: request.POST.get(name, "") for name in ("new_password1", "new_password2")}
        result = consume_password_reset_grant(grant_id=grant_id, raw_token=token, data=data)
        if isinstance(result, StyledSetPasswordForm):
            context.update(form=result, token=token)
        elif result is not None:
            context["reset_done"] = True
    else:
        context["form"] = password_reset_form(grant_id)
    # Native form POSTs can send Origin: null under no-referrer, failing CSRF validation.
    return _private_render(
        request, "accounts/password_reset_grant.html", context, referrer_policy="same-origin",
    )
