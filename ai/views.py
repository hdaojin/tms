from functools import cached_property
from uuid import uuid4

from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db.models import BooleanField, Q, Value, Case, When
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters, sensitive_variables
from django.views.generic import TemplateView, View
from django_tables2 import RequestConfig

from accounts.services.users import annotate_identity_labels, get_user_full_info, user_name_search_ids
from core.utils.breadcrumbs import breadcrumb_link
from core.utils.listing import FilterableListMixin, ListFilterSpec
from core.utils.mixins import SuperuserRequiredMixin, TitleMixin

from . import services
from .catalog import matching_option, provider_branding, provider_catalog
from .filters import ModelFilter
from .forms import AIModelForm, ModelDiscoveryForm, ModelOptionForm, ProviderDefaultForm, ShareModelForm
from .llm.discovery import fetch_model_ids
from .models import AIModelOption, AIModelPreference, AIProviderSettings, ThinkingMode
from .parameters import SAMPLING_PARAMETERS
from .providers import (
    ProviderError,
    provider_definition,
    provider_display_name,
    provider_names,
    validate_base_url,
    validate_model_id,
)
from .tables import ModelTable, ProviderTable


@method_decorator(never_cache, name="dispatch")
class ModelPage(PermissionRequiredMixin, TitleMixin, TemplateView):
    permission_required = services.VIEW
    title_icon = "icon-[tabler--settings]"


class ModelListView(FilterableListMixin, ModelPage):
    title = "我的 AI 模型"
    template_name = "ai/list.html"

    def get_list_filter_specs(self):
        specs = [ListFilterSpec("q", "搜索", "search", placeholder="搜索模型名称、模型 ID 或提供商")]
        for name in ("scope", "provider", "verified", "sharing"):
            field = self.model_filter.filters[name]
            specs.append(ListFilterSpec(name, field.label, "select", choices=field.extra["choices"],
                                        empty_label=f"全部{field.label}"))
        return specs

    @cached_property
    def model_filter(self):
        user = self.request.user
        can_manage = services.can_manage(user)
        scope = Q(pk__in=services.shared_models(user).values("pk"))
        if can_manage:
            scope |= Q(owner=user)
        models = services.AIModel.objects.filter(scope).select_related("owner", "owner__profile").defer(
            "encrypted_api_key", "base_url", "api_key_preview", "test_request", "test_reply"
        ).annotate(
            can_manage_record=Case(
                When(owner=user, then=Value(can_manage)), default=Value(False), output_field=BooleanField()
            ),
        )
        return ModelFilter(self.request.GET, queryset=models, request=self.request)

    def get_context_data(self, **kwargs):
        user = self.request.user
        can_manage = services.can_manage(user)
        preference = AIModelPreference.objects.filter(user=user).first()
        default_id = preference.model_id if preference else None
        usable_ids = set(services.usable_models(user).values_list("pk", flat=True))
        filters = self.model_filter
        table = ModelTable(filters.qs, provider_labels=filters.provider_labels)
        RequestConfig(self.request, paginate={"per_page": 25}).configure(table)
        table.context = {"default_id": default_id, "usable_ids": usable_ids, "request": self.request}
        if can_manage:
            kwargs["page_actions"] = [{"href": reverse("ai:create"), "label": "新增 AI 模型", "variant_class": "btn-primary"}]
        return super().get_context_data(
            can_manage=can_manage,
            filters=filters,
            table=table,

            default_id=default_id,
            default_unavailable=preference is not None and default_id not in usable_ids,
            usable_ids=usable_ids,
            **kwargs,
        )


class OwnerPage(ModelPage):
    permission_required = (services.VIEW, services.MANAGE_OWN)

    def get_breadcrumb_parents(self):
        return (breadcrumb_link("我的 AI 模型", "ai:list"),)

    def get_model(self):
        return get_object_or_404(
            services.own_models(self.request.user).defer("encrypted_api_key"), pk=self.kwargs["pk"]
        )


@method_decorator(sensitive_post_parameters("api_key"), name="dispatch")
class ModelEditView(OwnerPage):
    title = "新增 AI 模型"
    template_name = "ai/edit.html"

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
                return redirect("ai:detail", pk=model.pk)
        return self.render_to_response(self.get_context_data(form=form, model=model))


class CandidateVerificationView(OwnerPage):
    http_method_names = ["post"]

    def post(self, request):
        provider = request.POST.get("provider", "")
        address = request.POST.get("base_url", "")
        ids = request.POST.getlist("model_ids")
        if not address or len(address) > 300 or len(ids) > 400:
            return JsonResponse({"models": []}, status=400)
        try:
            address = validate_base_url(provider, address)
            models = {validate_model_id(value) for value in ids if len(value) <= 150}
        except ValidationError:
            return JsonResponse({"models": []}, status=400)
        verified = services.configured_models().filter(
            provider=provider, base_url=address, model_id__in=models, verified=True,
        ).order_by().values_list("model_id", flat=True).distinct()
        return JsonResponse({"models": list(verified)})


@method_decorator(sensitive_post_parameters("api_key"), name="dispatch")
class ModelDiscoveryView(OwnerPage):
    http_method_names = ["post"]

    @sensitive_variables()
    def post(self, request, pk=None):
        model = get_object_or_404(services.own_models(request.user), pk=pk) if pk is not None else None
        form = ModelDiscoveryForm(request.POST, model=model)
        if not form.is_valid():
            return JsonResponse({"error": next(iter(form.errors.values()))[0]}, status=400)
        provider = form.cleaned_data["provider"]
        base_url = form.cleaned_data["base_url"]
        key = form.cleaned_data["api_key"]
        adapter = provider_definition(provider)
        if not form.catalog[provider]["enabled"] or not adapter.model_list_path:
            return JsonResponse({"error": "此提供商当前不支持获取模型列表。"}, status=400)
        same_destination = model is not None and (provider, base_url) == (model.provider, model.base_url)
        if not key and not same_destination and adapter.key_required:
            return JsonResponse({"error": "请输入当前 API 地址的密钥。"}, status=400)
        if not cache.add(f"ai:model-discovery:{request.user.pk}", True, timeout=5):
            return JsonResponse({"error": "查询过于频繁，请稍候再试。"}, status=429)
        try:
            if not key and same_destination:
                key = services.model_key(model)
            ids = fetch_model_ids(provider, base_url, key)
        except ValidationError as exc:
            return JsonResponse({"error": exc.messages[0]}, status=400)
        except ProviderError as exc:
            return JsonResponse({"error": str(exc)}, status=502)
        return JsonResponse({"models": ids})


def model_action_context(user, model):
    return {
        "share_form": ShareModelForm(model=model),
        "can_set_default": services.usable_models(user).filter(pk=model.pk).exists(),
        "is_default": AIModelPreference.objects.filter(user=user, model=model).exists(),
    }


class ModelDetailView(OwnerPage):
    title = "AI 模型与连接测试"
    template_name = "ai/detail.html"

    def get_context_data(self, **kwargs):
        model = kwargs.get("model") or self.get_model()
        entry = provider_catalog().get(model.provider, {})
        option = matching_option(entry, model.base_url, model.model_id)
        capabilities = []
        if option:
            capabilities.append("文本生成")
            if option["images"] and (not option.get("builtin") or model.base_url == entry["official"]):
                capabilities.append("图片输入")
            if option["json"]:
                capabilities.append("JSON 输出")
            if "thinking" in option["presets"]:
                capabilities.append("思考模式")
        parameters = [
            (label, model.request_parameters[name])
            for name, (label, _, _) in SAMPLING_PARAMETERS.items() if name in model.request_parameters
        ]
        if model.thinking == ThinkingMode.ENABLED or (option and "thinking" in option["presets"]):
            parameters.append(("思考模式", model.get_thinking_display() or "使用接口默认值"))
            if model.reasoning_effort:
                parameters.append(("思考强度", model.get_reasoning_effort_display()))
        return super().get_context_data(
            **{
                **model_action_context(self.request.user, model),
                "model": model,
                "capabilities": capabilities,
                "capability_source": ("内置能力" if option.get("builtin") else "提供商目录") if option else "",
                "parameters": parameters,
                **kwargs,
            },
        )


class ModelShareView(ModelDetailView):
    http_method_names = ["post"]

    def post(self, request, pk):
        model = self.get_model()
        form = ShareModelForm(request.POST, model=model)
        if form.is_valid():
            data = form.cleaned_data
            mode = data["mode"]
            try:
                services.set_shared(
                    request.user, pk, mode != "private", audience=mode,
                    user_ids=[user.pk for user in data["users"]],
                    group_ids=[group.pk for group in data["groups"]],
                )
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                messages.success(request, "共享设置已保存。")
                return redirect("ai:detail", pk=pk)
        return self.render_to_response(self.get_context_data(model=model, share_form=form))


@method_decorator(never_cache, name="dispatch")
class ShareRecipientSearchView(PermissionRequiredMixin, View):
    permission_required = (services.VIEW, services.MANAGE_OWN)

    def get(self, request, pk):
        get_object_or_404(services.own_models(request.user).only("pk"), pk=pk)
        query = request.GET.get("q", "").strip()
        try:
            page = int(request.GET.get("page", "1"))
        except ValueError:
            page = 0
        if len(query) > 100 or not 1 <= page <= 10000:
            return JsonResponse({"error": "搜索条件无效，请重新输入。"}, status=400)
        if not query:
            return JsonResponse({"results": [], "has_more": False})
        eligible = services.share_recipients()
        matches = annotate_identity_labels(eligible).filter(pk__in=user_name_search_ids(eligible, query))
        users = list(matches.order_by("last_name", "first_name", "pk")[(page - 1) * 20 : page * 20 + 1])
        return JsonResponse({
            "results": [
                {"id": user.pk, "label": get_user_full_info(user), "invalid": user.identity_invalid}
                for user in users[:20]
            ],
            "has_more": len(users) > 20,
        })


class ModelDeleteView(OwnerPage):
    title = "删除 AI 模型"
    template_name = "ai/delete.html"

    def get_context_data(self, **kwargs):
        return super().get_context_data(model=self.get_model(), **kwargs)

    def post(self, request, *args, **kwargs):
        services.delete_model(request.user, kwargs["pk"])
        messages.success(request, "AI 模型已删除。")
        return redirect("ai:list")


class ModelTestView(PermissionRequiredMixin, View):
    permission_required = (services.VIEW, services.MANAGE_OWN)

    def post(self, request, pk):
        try:
            error = services.test_model(request.user, pk)
            notice = error or "测试成功，模型已返回文本。"
        except ValidationError as exc:
            error = notice = exc.messages[0]
        if request.htmx:
            model = get_object_or_404(services.own_models(request.user).defer("encrypted_api_key"), pk=pk)
            return render(request, "ai/detail.html#connection_actions", {
                "model": model, "test_notice": notice, "test_failed": bool(error),
                "update_connection_badge": True,
                **model_action_context(request.user, model),
            })
        if error:
            messages.error(request, notice)
        else:
            messages.success(request, notice)
        return redirect("ai:detail", pk=pk)


class DefaultModelView(PermissionRequiredMixin, View):
    permission_required = services.VIEW

    def post(self, request, pk):
        try:
            services.set_default_model(request.user, pk)
        except ValidationError as exc:
            messages.error(request, exc.messages[0])
        else:
            messages.success(request, "默认 AI 模型已更新。")
        if request.POST.get("from_detail") and services.can_manage(request.user) and services.own_models(request.user).filter(pk=pk).exists():
            return redirect("ai:detail", pk=pk)
        return redirect("ai:list")


class ModerationView(ModelPage):
    title = "共享 AI 模型管理"
    template_name = "ai/moderation.html"

    def get_context_data(self, **kwargs):
        models = list(
            services.moderated_models(self.request.user)
            .select_related("owner")
            .only("name", "provider", "custom_provider_name", "model_id", "owner", "is_delisted")
        )
        names = provider_names()
        for model in models:
            model.provider_name = provider_display_name(model.provider, model.custom_provider_name, names)
        return super().get_context_data(models=models, **kwargs)


class ModerationActionView(View):
    def post(self, request, pk, delisted):
        services.moderate_model(request.user, pk, delisted)
        messages.success(request, "共享模型已下架。" if delisted else "已解除下架，所有者可重新开启共享。")
        return redirect("ai:moderation")


@method_decorator(never_cache, name="dispatch")
class ProviderPage(SuperuserRequiredMixin, TitleMixin, TemplateView):
    title_icon = "icon-[tabler--settings]"

    @cached_property
    def provider_entry(self):
        code = self.kwargs["provider"]
        adapter = provider_definition(code)
        if adapter is None:
            raise Http404
        return code, adapter

    @property
    def definition(self):
        return self.provider_entry[1]

    def get_provider(self):
        return self.provider_entry[0]

    def get_breadcrumb_parents(self):
        return (breadcrumb_link("AI 模型提供商", "ai:providers"),)


class ProviderListView(ProviderPage):
    title = "AI 模型提供商"
    template_name = "ai/provider_list.html"

    def get_context_data(self, **kwargs):
        rows = [
            dict(
                code=code, label=entry["label"], provider_key=entry["provider_key"], protocol=entry["protocol"],
                default_url=entry["default"], default_model=entry["default_model"],
                default_model_label=entry.get("default_model_label", ""), model_count=len(entry["models"]),
                enabled=entry["enabled"],
            )
            for code, entry in provider_catalog().items()
        ]
        table = ProviderTable(rows)
        RequestConfig(self.request, paginate={"per_page": 25}).configure(table)
        kwargs["page_actions"] = [
            {"href": reverse("ai:provider_create"), "label": "新增模型提供商", "variant_class": "btn-primary"}
        ]
        return super().get_context_data(table=table, **kwargs)

    def get_breadcrumb_parents(self):
        return ()


class ProviderCreateView(ProviderPage):
    title = "新增模型提供商"
    template_name = "common/form.html"

    def get_context_data(self, **kwargs):
        kwargs.setdefault("form", ProviderDefaultForm())
        return super().get_context_data(**kwargs)

    def post(self, request, *args, **kwargs):
        form = ProviderDefaultForm(request.POST, request.FILES)
        if form.is_valid():
            settings = AIProviderSettings.objects.create(provider=uuid4().hex, **form.cleaned_data)
            messages.success(request, "模型提供商已新增。")
            return redirect("ai:provider", provider=settings.provider)
        return self.render_to_response(self.get_context_data(form=form))


class ProviderCatalogView(ProviderPage):
    template_name = "ai/providers.html"

    def get_title(self):
        return f"{self.definition.label} 配置"

    def get_context_data(self, **kwargs):
        provider = self.get_provider()
        options = AIModelOption.objects.filter(provider=provider)
        adapter = self.definition
        defaults = AIProviderSettings.objects.filter(provider=provider).first() or AIProviderSettings()
        if "form" not in kwargs:
            kwargs["form"] = ProviderDefaultForm(
                provider=provider,
                initial={
                    "enabled": defaults.enabled,
                    "name": defaults.name,
                    "default_base_url": defaults.default_base_url,
                },
            )
        kwargs.update(
            provider=provider,
            options=options,
            branding=provider_branding(provider, defaults, adapter),
            provider_key=adapter.route,
            builtin_model=adapter.default_model,
            show_builtin=bool(adapter.default_model) and not options.exists(),
        )
        return super().get_context_data(**kwargs)

    def post(self, request, *args, **kwargs):
        provider = self.get_provider()
        form = ProviderDefaultForm(request.POST, request.FILES, provider=provider)
        if form.is_valid():
            defaults = form.cleaned_data
            logo = defaults.pop("logo", None)
            if defaults.pop("remove_logo", False):
                defaults["logo"] = ""
            elif logo:
                defaults["logo"] = logo
            if "enabled_present" not in request.POST and "enabled" not in request.POST:
                defaults.pop("enabled", None)
            AIProviderSettings.objects.update_or_create(provider=provider, defaults=defaults)
            messages.success(request, "提供商默认设置已保存。")
            return redirect("ai:provider", provider=provider)
        return self.render_to_response(self.get_context_data(form=form))


class ProviderOptionView(ProviderPage):
    title = "新增 AI 模型选项"
    template_name = "ai/model_option_form.html"

    def get_title(self):
        return "编辑 AI 模型选项" if {"pk", "fallback"} & self.kwargs.keys() else super().get_title()

    def get_breadcrumb_parents(self):
        provider = self.get_provider()
        return (
            breadcrumb_link("AI 模型提供商", "ai:providers"),
            breadcrumb_link(f"{self.definition.label} 配置", "ai:provider", kwargs={"provider": provider}),
        )

    def get_option(self, provider):
        if "pk" in self.kwargs:
            return get_object_or_404(AIModelOption, pk=self.kwargs["pk"], provider=provider)
        if self.kwargs.get("fallback") and (
            not self.definition.default_model or AIModelOption.objects.filter(provider=provider).exists()
        ):
            raise Http404
        return None

    def get_context_data(self, **kwargs):
        return super().get_context_data(provider_key=self.definition.route, **kwargs)

    def get(self, request, *args, **kwargs):
        provider = self.get_provider()
        option = self.get_option(provider)
        if kwargs.get("fallback"):
            adapter = self.definition
            fallback = provider_catalog(provider)[provider]
            existing = matching_option(fallback, fallback["default"], adapter.default_model)
            option = AIModelOption(
                model_id=adapter.default_model,
                name=adapter.default_model,
                is_default=True,
                supports_images=bool(existing and existing["images"]),
                supports_json=bool(existing and existing["json"]),
                parameter_presets=existing["presets"] if existing else {},
            )
        form = ModelOptionForm(provider=provider, option=option)
        return self.render_to_response(self.get_context_data(form=form))

    def post(self, request, *args, **kwargs):
        provider = self.get_provider()
        option = self.get_option(provider)
        form = ModelOptionForm(request.POST, provider=provider, option=option)
        if form.is_valid():
            try:
                services.save_model_option(request.user, provider, form.cleaned_data, self.kwargs.get("pk"))
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                messages.success(request, "模型选项已保存。")
                return redirect("ai:provider", provider=provider)
        return self.render_to_response(self.get_context_data(form=form))
