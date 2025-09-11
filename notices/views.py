from django.db.models.base import Model as Model
from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import CreateView, DetailView, ListView, DeleteView
from django.urls import reverse_lazy
from django.http import Http404

from .models import Notice, NoticeAttachment
from .forms import NoticeForm


def _get_notices_with_read_status(user):
    """
    获取用户有权限查看的通知查询集
    """
    # 用户组ID列表
    user_group_ids = list(user.groups.values_list('id', flat=True))

    # 可见性规则：作者始终可见；其他用户需满足（有发布时间 且 未限定或在目标组）
    author_q = Q(published_by=user)
    if user_group_ids:
        published_visible_q = Q(published_at__isnull=False) & (
            Q(target_groups__isnull=True) | Q(target_groups__in=user_group_ids)
        )
    else:
        published_visible_q = Q(published_at__isnull=False) & Q(target_groups__isnull=True)

    notices = (
        Notice.objects
        .filter(author_q | published_visible_q)
        .prefetch_related('attachments')
        .distinct()
        .order_by('-published_at', '-id')
    )

    return notices


class NoticeListView(LoginRequiredMixin, ListView):
    model = Notice
    template_name = 'notices/notice_list.html'
    partial_template_name = 'notices/notice_list_partial.html'
    context_object_name = 'notices'
    paginate_by = 10
    extra_context = {
        "title": "通知列表",
        "title_icon" : "icon-[tabler--list]"
    }

    def get_queryset(self):
        return _get_notices_with_read_status(self.request.user)

    def get_template_names(self):
        # django-htmx：HTMX 请求返回局部模板，其余返回整页模板
        if self.request.htmx:      # type: ignore
            return [self.partial_template_name]
        return [self.template_name]

    
class NoticeDetailView(LoginRequiredMixin, DetailView):
    model = Notice
    template_name = 'notices/notice_detail.html'
    context_object_name = 'notice'
    extra_context = {
        "title": "通知详情",
        "title_icon" : "icon-[tabler--bell]"
    }

    def get_queryset(self):
        return _get_notices_with_read_status(self.request.user)


class NoticeDeleteView(LoginRequiredMixin, DeleteView):
    model = Notice
    success_url = reverse_lazy('notices:notice_list')
    extra_context = {
        "title": "删除通知",
        "title_icon" : "icon-[tabler--trash]"
    }

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        # 仅允许发布者本人删除
        if self.request.user != obj.published_by:     # type: ignore
            raise Http404
        return obj



class NoticeCreateView(LoginRequiredMixin, CreateView):
    model = Notice
    form_class = NoticeForm
    template_name = 'notices/notice_create.html'
    success_url = reverse_lazy('notices:notice_list')
    extra_context = {
        "title": "发布通知",
        "title_icon" : "icon-[tabler--plus]"
    }
    def form_valid(self, form):
        form.instance.published_by = self.request.user
        # 直接发布：设置发布时间
        if not form.instance.published_at:
            form.instance.published_at = timezone.now()

        attachments = self.request.FILES.getlist('attachments')
        with transaction.atomic():
            response = super().form_valid(form)
            obj = getattr(self, 'object', None)
            if attachments and obj is not None:
                objs = []
                for f in attachments:
                    if not f:
                        continue
                    na = NoticeAttachment(notice=obj, file=f)
                    # bulk_create 不会触发 save()，这里显式填充文件大小
                    try:
                        na.file_size = getattr(f, 'size', None)
                    except Exception:
                        pass
                    objs.append(na)
                if objs:
                    NoticeAttachment.objects.bulk_create(objs)
        if obj is not None:
            messages.success(self.request, "通知已发布成功！")
        return response