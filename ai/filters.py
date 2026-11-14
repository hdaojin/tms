import django_filters
from django import forms
from django.db.models import Q

from core.utils.forms import StyledFormMixin

from .models import AIModel
from .providers import PROVIDERS


class ModelFilterForm(StyledFormMixin, forms.Form):
    pass


class ModelFilter(django_filters.FilterSet):
    q = django_filters.CharFilter(label="搜索", method="search")
    scope = django_filters.ChoiceFilter(
        label="模型范围", choices=[("own", "我的"), ("shared", "共享")], method="scope_filter"
    )
    provider = django_filters.ChoiceFilter(
        label="模型提供商", choices=[(code, provider.label) for code, provider in PROVIDERS.items()]
    )
    verified = django_filters.ChoiceFilter(
        label="验证状态", choices=[("yes", "已验证"), ("no", "待验证")], method="validation_filter"
    )
    sharing = django_filters.ChoiceFilter(
        label="共享状态",
        choices=[("private", "私有"), ("all", "全体共享"), ("selected", "定向共享"), ("delisted", "已下架")],
        method="sharing_filter",
    )

    class Meta:
        model = AIModel
        fields = []
        form = ModelFilterForm

    def search(self, queryset, name, value):
        providers = [code for code, provider in PROVIDERS.items() if value.casefold() in provider.label.casefold()]
        return queryset.filter(
            Q(name__icontains=value) | Q(model_id__icontains=value) | Q(provider__icontains=value) | Q(provider__in=providers)
        )

    def scope_filter(self, queryset, name, value):
        return queryset.filter(can_manage_record=value == "own")

    def validation_filter(self, queryset, name, value):
        return queryset.filter(verified=value == "yes")

    def sharing_filter(self, queryset, name, value):
        if value == "delisted":
            return queryset.filter(is_delisted=True)
        if value == "private":
            return queryset.filter(is_shared=False, is_delisted=False)
        return queryset.filter(is_shared=True, share_audience=value)
