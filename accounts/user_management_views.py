from django.contrib import messages
from django import forms
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.shortcuts import get_object_or_404, redirect
from django.http import QueryDict
from django.urls import reverse
from django.views.generic import TemplateView
from django.contrib.auth import get_user_model

from accounts.services.user_management import (
    PARAMETER_OPERATIONS,
    filter_users,
    load_user_action,
    normalize_ids,
    prepare_user_action,
    preview_users,
    save_users,
)
from accounts.user_management_forms import UserActionForm, UserFilterForm, UserManagementForm
from core.utils.mixins import SuperuserRequiredMixin, TitleMixin


class UserManagementView(SuperuserRequiredMixin, TitleMixin, TemplateView):
    template_name = "accounts/user_management.html"
    title = "用户管理预览"
    title_icon = "icon-[tabler--users]"

    def test_func(self):
        return self.request.user.is_active and self.request.user.is_superuser

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query = kwargs.get("return_query", self.request.POST.get("return_query", ""))
        params = QueryDict(query)
        safe_params = QueryDict(mutable=True)
        for key in ("q", "active", "role", "sort", "page"):
            if key in params:
                safe_params.setlist(key, params.getlist(key))
        context["return_query"] = safe_params.urlencode()
        context["return_url"] = reverse("accounts:user_list")
        if context["return_query"]:
            context["return_url"] += "?" + context["return_query"]
        return context

    def get_selected_ids(self):
        if "pk" in self.kwargs:
            return [get_object_or_404(get_user_model(), pk=self.kwargs["pk"]).pk]
        if self.request.POST.get("selection") == "all":
            filters = UserFilterForm(self.request.POST)
            if not filters.is_valid():
                raise ValidationError("筛选条件无效，请返回列表重新选择，操作未执行。")
            return normalize_ids(
                filter_users(get_user_model().objects.all(), filters.cleaned_data).values_list("pk", flat=True)
            )
        if self.request.POST.get("selection") == "selected":
            return normalize_ids(self.request.POST.getlist("users"))
        raise ValidationError("请选择当前页用户或全部匹配用户。")

    def parameter_context(self, selection, data=None):
        operation = selection["operation"]
        form = UserManagementForm(data=data, initial={"operation": operation})
        form.fields["operation"].widget = forms.HiddenInput()
        parameter = "leave_date" if operation == "set_leave_date" else "roles"
        del form.fields["roles" if parameter == "leave_date" else "leave_date"]
        return self.get_context_data(
            form=form,
            parameter_selection=selection,
            operation_label=dict(UserManagementForm.base_fields["operation"].choices)[operation],
            return_query=selection["return_query"],
        )

    def get_success_url(self):
        # 操作可能减少当前筛选结果；尽量保留页码，避免回到已不存在的页。
        from accounts.views import UserListView

        params = QueryDict(self.get_context_data()["return_query"], mutable=True)
        try:
            page = int(params.get("page", "1"))
        except ValueError:
            return self.get_context_data()["return_url"]
        filters = UserFilterForm(params)
        count = filter_users(get_user_model().objects.all(), filters.cleaned_data).count() if filters.is_valid() else 0
        last_page = max(1, (count + UserListView.paginate_by - 1) // UserListView.paginate_by)
        if page > last_page:
            params["page"] = str(last_page)
        return self.get_context_data(return_query=params.urlencode())["return_url"]

    def get(self, request, *args, **kwargs):
        if "pk" not in kwargs:
            return redirect(self.get_context_data()["return_url"])
        target = get_object_or_404(get_user_model(), pk=kwargs["pk"])
        choices = UserManagementForm.base_fields["operation"].choices
        profile = getattr(target, "profile", None)
        form = UserManagementForm(
            initial={"operation": "set_leave_date", "leave_date": profile.leave_date if profile else None}
        )
        form.fields["operation"].choices = [
            choice for choice in choices if choice[0] not in ("add_roles", "remove_roles")
        ]
        del form.fields["roles"]
        return self.render_to_response(self.get_context_data(form=form, target_user=target))

    def post(self, request, *args, **kwargs):
        if request.POST.get("action") == "save":
            try:
                result = save_users(
                    actor=request.user, token=request.POST.get("preview_token", ""), target_id=kwargs.get("pk")
                )
            except ValidationError as exc:
                return self.render_to_response(self.get_context_data(errors=exc.messages), status=400)
            except IntegrityError:
                return self.render_to_response(
                    self.get_context_data(errors=["保存时发生数据冲突，操作已回滚，请重新预览。"]),
                    status=400,
                )
            messages.success(request, f"已处理 {result['count']} 位用户，实际修改 {result['changed']} 位。")
            if "pk" in kwargs:
                return redirect("accounts:user_detail", pk=kwargs["pk"])
            return redirect(self.get_success_url())
        try:
            if request.POST.get("parameter_token") and "pk" not in kwargs:
                selection = load_user_action(actor=request.user, token=request.POST["parameter_token"])
                if request.POST.get("operation") != selection["operation"]:
                    raise ValidationError("操作与已选择的名单不一致，请重新选择。")
                context = self.parameter_context(selection, data=request.POST)
                form = context["form"]
                if not form.is_valid():
                    return self.render_to_response(context, status=400)
                preview = preview_users(actor=request.user, ids=selection["ids"], payload=form.payload())
                return self.render_to_response(
                    self.get_context_data(preview=preview, return_query=selection["return_query"])
                )

            action_form = UserActionForm(request.POST)
            if not action_form.is_valid():
                raise ValidationError([message for errors in action_form.errors.values() for message in errors])
            operation = action_form.cleaned_data["operation"]
            ids = self.get_selected_ids()
            if "pk" not in kwargs and operation in PARAMETER_OPERATIONS:
                selection = prepare_user_action(
                    actor=request.user,
                    ids=ids,
                    operation=operation,
                    return_query=self.get_context_data()["return_query"],
                )
                return self.render_to_response(self.parameter_context(selection))

            form = UserManagementForm(request.POST)
            if not form.is_valid():
                raise ValidationError([message for errors in form.errors.values() for message in errors])
            if "pk" in kwargs:
                if form.cleaned_data["operation"] in ("add_roles", "remove_roles"):
                    raise ValidationError("请使用用户角色分配页面。")
            preview = preview_users(actor=request.user, ids=ids, payload=form.payload())
        except ValidationError as exc:
            return self.render_to_response(self.get_context_data(errors=exc.messages), status=400)
        return self.render_to_response(self.get_context_data(preview=preview))
