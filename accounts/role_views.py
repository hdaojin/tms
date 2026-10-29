from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import FormView, TemplateView

from accounts.role_forms import RoleForm, UserRolesForm
from accounts.selectors import permission_diagnostics
from accounts.services.roles import preview_role, role_initial, save_role, preview_user_roles, save_user_roles
from core.permissions import get_permission_bundle_spec_map
from core.utils.breadcrumbs import breadcrumb_link
from core.utils.mixins import SuperuserRequiredMixin, TitleMixin


class RoleEditView(SuperuserRequiredMixin, TitleMixin, FormView):
    form_class = RoleForm
    template_name = "accounts/role_form.html"
    title = "配置角色权限"
    title_icon = "icon-[tabler--users]"
    copying = False

    def get_source(self):
        if not hasattr(self, "source"):
            self.source = get_object_or_404(Group, pk=self.kwargs["pk"]) if "pk" in self.kwargs else None
        return self.source

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        source = self.get_source()
        kwargs["group"] = None if self.copying else source
        kwargs["initial"] = role_initial(source, copying=self.copying)
        return kwargs

    def get_breadcrumb_parents(self):
        return [breadcrumb_link("角色列表", "accounts:role_list")]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        specs = get_permission_bundle_spec_map()
        groups = {}
        for option in context["form"]["bundles"]:
            spec = specs[option.data["value"]]
            category = spec.name.split(" | ", 1)[0]
            groups.setdefault(category, []).append({"option": option, "spec": spec})
        context["bundle_groups"] = groups.items()
        context["copying"] = self.copying
        context["source_group"] = self.get_source()
        return context

    def form_valid(self, form):
        group = None if self.copying else self.get_source()
        payload = form.payload()
        if self.request.POST.get("action") == "save":
            try:
                saved = save_role(
                    actor=self.request.user,
                    group=group,
                    payload=payload,
                    token=self.request.POST.get("preview_token", ""),
                )
            except (ValidationError, IntegrityError) as exc:
                form.add_error(None, exc if isinstance(exc, ValidationError) else "保存时发生冲突，请重新预览。")
                return self.form_invalid(form)
            messages.success(self.request, "角色权限、领域和成员已保存。")
            return redirect("accounts:role_edit", pk=saved.pk)
        preview = preview_role(actor=self.request.user, group=group, payload=payload)
        return self.render_to_response(self.get_context_data(form=form, preview=preview))


class UserPermissionView(SuperuserRequiredMixin, TitleMixin, TemplateView):
    template_name = "accounts/user_permissions.html"
    title = "用户有效权限诊断"
    title_icon = "icon-[tabler--users]"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        target = get_object_or_404(get_user_model(), pk=self.kwargs["pk"])
        context.update(target_user=target, diagnostics=permission_diagnostics(target))
        return context

    def get_breadcrumb_parents(self):
        return [breadcrumb_link("用户列表", "accounts:user_list")]


class UserRolesView(SuperuserRequiredMixin, TitleMixin, FormView):
    form_class = UserRolesForm
    template_name = "accounts/user_roles.html"
    title = "分配角色"
    title_icon = "icon-[tabler--users]"

    def get_target(self):
        if not hasattr(self, "target"):
            self.target = get_object_or_404(get_user_model(), pk=self.kwargs["pk"])
        return self.target

    def get_initial(self):
        return {"roles": list(self.get_target().groups.values_list("pk", flat=True))}

    def get_context_data(self, **kwargs):
        return super().get_context_data(target_user=self.get_target(), **kwargs)

    def get_breadcrumb_parents(self):
        return [breadcrumb_link("用户列表", "accounts:user_list")]

    def form_valid(self, form):
        role_ids = [group.pk for group in form.cleaned_data["roles"]]
        try:
            if self.request.POST.get("action") == "save":
                user = save_user_roles(
                    actor=self.request.user,
                    user=self.get_target(),
                    role_ids=role_ids,
                    token=self.request.POST.get("preview_token", ""),
                )
                messages.success(self.request, "用户所属角色已保存，个人直接授权保持不变。")
                return redirect("accounts:user_roles", pk=user.pk)
            preview = preview_user_roles(actor=self.request.user, user=self.get_target(), role_ids=role_ids)
        except ValidationError as exc:
            form.add_error(None, exc)
            return self.form_invalid(form)
        return self.render_to_response(self.get_context_data(form=form, preview=preview))
