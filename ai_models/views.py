from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters, sensitive_variables
from django.views.generic import TemplateView, View

from core.utils.breadcrumbs import breadcrumb_link
from core.utils.mixins import SuperuserRequiredMixin, TitleMixin

from . import services
from .catalog import provider_catalog
from .forms import AIModelForm, ModelOptionForm, ProviderDefaultForm, ShareModelForm
from .models import AIModelOption, AIModelPreference, AIProviderSettings, ReasoningEffort
from .providers import PROVIDERS


@method_decorator(never_cache, name="dispatch")
class ModelPage(PermissionRequiredMixin, TitleMixin, TemplateView):
    permission_required = services.VIEW
    title_icon = "icon-[tabler--settings]"


class ModelListView(ModelPage):
    title = "我的 AI 模型"
    template_name = "ai_models/list.html"

    def get_context_data(self, **kwargs):
        user = self.request.user
        can_manage = services.can_manage(user)
        can_use_shared = services.can_use_shared(user)
        preference = AIModelPreference.objects.filter(user=user).first()
        default_id = preference.model_id if preference else None
        usable_ids = set(services.usable_models(user).values_list("pk", flat=True))
        public_models = ()
        if can_use_shared:
            public_models = (
                services.shared_models().select_related("owner").only("name", "provider", "model_id", "owner")
            )
            if can_manage:
                public_models = public_models.exclude(owner=user)
        return super().get_context_data(
            can_manage=can_manage,
            can_use_shared=can_use_shared,
            own_models=services.own_models(user).defer("encrypted_api_key") if can_manage else (),
            public_models=public_models,
            default_id=default_id,
            default_unavailable=preference is not None and default_id not in usable_ids,
            usable_ids=usable_ids,
            **kwargs,
        )


class OwnerPage(ModelPage):
    permission_required = (services.VIEW, services.MANAGE_OWN)

    def get_breadcrumb_parents(self):
        return (breadcrumb_link("我的 AI 模型", "ai_models:list"),)

    def get_model(self):
        return get_object_or_404(
            services.own_models(self.request.user).defer("encrypted_api_key"), pk=self.kwargs["pk"]
        )


@method_decorator(sensitive_post_parameters("api_key"), name="dispatch")
class ModelEditView(OwnerPage):
    title = "新增 AI 模型"
    template_name = "ai_models/edit.html"

    def get_title(self):
        return "编辑 AI 模型" if "pk" in self.kwargs else super().get_title()

    def get(self, request, *args, **kwargs):
        model = self.get_model() if "pk" in kwargs else None
        return self.render_to_response(self.get_context_data(form=AIModelForm(model=model), model=model))

    @sensitive_variables()
    def post(self, request, *args, **kwargs):
        model = self.get_model() if "pk" in kwargs else None
        form = AIModelForm(request.POST, model=model)
        if form.is_valid():
            try:
                model = services.save_model(request.user, form.cleaned_data, kwargs.get("pk"))
            except ValidationError as exc:
                if hasattr(exc, "error_dict"):
                    for field, errors in exc.error_dict.items():
                        form.add_error(field, errors)
                else:
                    form.add_error(None, exc)
            else:
                messages.success(request, "AI 模型已保存。")
                return redirect("ai_models:detail", pk=model.pk)
        return self.render_to_response(self.get_context_data(form=form, model=model))


class ModelDetailView(OwnerPage):
    title = "AI 模型与连接测试"
    template_name = "ai_models/detail.html"

    def get_context_data(self, **kwargs):
        model = self.get_model()
        return super().get_context_data(
            model=model, share_form=ShareModelForm(initial={"is_shared": model.is_shared}), **kwargs
        )


class ModelDeleteView(OwnerPage):
    title = "删除 AI 模型"
    template_name = "ai_models/delete.html"

    def get_context_data(self, **kwargs):
        return super().get_context_data(model=self.get_model(), **kwargs)

    def post(self, request, *args, **kwargs):
        services.delete_model(request.user, kwargs["pk"])
        messages.success(request, "AI 模型已删除。")
        return redirect("ai_models:list")


class ModelActionView(PermissionRequiredMixin, View):
    permission_required = (services.VIEW, services.MANAGE_OWN)

    def post(self, request, pk, action):
        try:
            if action == "test":
                error = services.test_model(request.user, pk)
                if error:
                    messages.error(request, error)
                else:
                    messages.success(request, "测试成功，模型已返回文本。")
            else:
                form = ShareModelForm(request.POST)
                if not form.is_valid():
                    raise ValidationError("请选择有效的共享状态。")
                shared = form.cleaned_data["is_shared"]
                services.set_shared(request.user, pk, shared)
                messages.success(request, "已开启共享。" if shared else "已取消共享。")
        except ValidationError as exc:
            messages.error(request, exc.messages[0])
        return redirect("ai_models:detail", pk=pk)


class DefaultModelView(PermissionRequiredMixin, View):
    permission_required = services.VIEW

    def post(self, request, pk):
        try:
            services.set_default_model(request.user, pk)
        except ValidationError as exc:
            messages.error(request, exc.messages[0])
        else:
            messages.success(request, "默认 AI 模型已更新。")
        return redirect("ai_models:list")


class ModerationView(ModelPage):
    title = "公共 AI 模型管理"
    template_name = "ai_models/moderation.html"

    def get_context_data(self, **kwargs):
        models = (
            services.moderated_models(self.request.user)
            .select_related("owner")
            .only("name", "provider", "model_id", "owner", "is_delisted")
        )
        return super().get_context_data(models=models, **kwargs)


class ModerationActionView(View):
    def post(self, request, pk, delisted):
        services.moderate_model(request.user, pk, delisted)
        messages.success(request, "公共模型已下架。" if delisted else "已解除下架，所有者可重新开启共享。")
        return redirect("ai_models:moderation")


@method_decorator(never_cache, name="dispatch")
class ProviderPage(SuperuserRequiredMixin, TitleMixin, TemplateView):
    title_icon = "icon-[tabler--settings]"

    def get_provider(self):
        code = self.kwargs["provider"]
        if code not in PROVIDERS:
            raise Http404
        return code


class ProviderListView(ProviderPage):
    title = "AI 模型提供商"
    template_name = "ai_models/provider_list.html"

    def get_context_data(self, **kwargs):
        catalog = provider_catalog()
        providers = [(code, adapter.label, catalog[code]) for code, adapter in PROVIDERS.items()]
        return super().get_context_data(providers=providers, **kwargs)


class ProviderCatalogView(ProviderPage):
    template_name = "ai_models/providers.html"

    def get_title(self):
        return f"{PROVIDERS[self.get_provider()].label} 配置"

    def get_breadcrumb_parents(self):
        return (breadcrumb_link("AI 模型提供商", "ai_models:providers"),)

    def get_context_data(self, **kwargs):
        provider = self.get_provider()
        options = AIModelOption.objects.filter(provider=provider)
        adapter = PROVIDERS[provider]
        if "form" not in kwargs:
            defaults = AIProviderSettings.objects.filter(provider=provider).first() or AIProviderSettings()
            kwargs["form"] = ProviderDefaultForm(
                provider=provider,
                initial={
                    "default_base_url": defaults.default_base_url,
                    "thinking": defaults.thinking,
                    "reasoning_effort": defaults.reasoning_effort or ReasoningEffort.HIGH,
                },
            )
        kwargs.update(
            provider=provider,
            options=options,
            builtin_model=adapter.default_model,
            show_builtin=not options.exists(),
        )
        return super().get_context_data(**kwargs)

    def post(self, request, *args, **kwargs):
        provider = self.get_provider()
        form = ProviderDefaultForm(request.POST, provider=provider)
        if form.is_valid():
            AIProviderSettings.objects.update_or_create(provider=provider, defaults=form.cleaned_data)
            messages.success(request, "提供商默认设置已保存。")
            return redirect("ai_models:provider", provider=provider)
        return self.render_to_response(self.get_context_data(form=form))


class ProviderOptionView(ProviderPage):
    title = "新增 AI 模型选项"
    template_name = "common/form.html"

    def get_title(self):
        return "编辑 AI 模型选项" if {"pk", "fallback"} & self.kwargs.keys() else super().get_title()

    def get_breadcrumb_parents(self):
        provider = self.get_provider()
        return (
            breadcrumb_link("AI 模型提供商", "ai_models:providers"),
            breadcrumb_link(f"{PROVIDERS[provider].label} 配置", "ai_models:provider", kwargs={"provider": provider}),
        )

    def get_option(self, provider):
        if "pk" in self.kwargs:
            return get_object_or_404(AIModelOption, pk=self.kwargs["pk"], provider=provider)
        return None

    def get(self, request, *args, **kwargs):
        provider = self.get_provider()
        option = self.get_option(provider)
        if kwargs.get("fallback"):
            adapter = PROVIDERS[provider]
            option = AIModelOption(model_id=adapter.default_model, name=adapter.default_model, is_default=True)
        form = ModelOptionForm(option=option)
        return self.render_to_response(self.get_context_data(form=form))

    def post(self, request, *args, **kwargs):
        provider = self.get_provider()
        option = self.get_option(provider)
        form = ModelOptionForm(request.POST, option=option)
        if form.is_valid():
            try:
                services.save_model_option(request.user, provider, form.cleaned_data, self.kwargs.get("pk"))
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                messages.success(request, "模型选项已保存。")
                return redirect("ai_models:provider", provider=provider)
        return self.render_to_response(self.get_context_data(form=form))
