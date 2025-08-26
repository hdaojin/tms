from django.shortcuts import render, get_object_or_404, redirect
from django.core.paginator import Paginator
from django.contrib.auth.decorators import permission_required
from django.contrib import messages
from django.db.models import Q
from django.utils import timezone

from .models import Notice, NoticeAttachment
from .forms import NoticeForm


def _get_notices_with_read_status(user):
    """
    获取用户有权限查看的通知查询集
    """
    # 用户组ID列表
    user_group_ids = list(user.groups.values_list('id', flat=True))
    
    # 过滤条件：
    # 1. 通知已发布
    # 2. 没有指定目标组（向所有人发送）或用户在目标组中
    notices = Notice.objects.filter(is_published=True).prefetch_related('attachments')
    
    if user_group_ids:
        # 如果用户有组，则显示：无目标组的通知 或 用户组在目标组中的通知
        notices = notices.filter(
            Q(target_groups__isnull=True) | 
            Q(target_groups__in=user_group_ids)
        )
    else:
        # 如果用户没有组，只显示没有指定目标组的通知
        notices = notices.filter(target_groups__isnull=True)
    
    return notices.distinct().order_by('-published_at', '-updated_at')


def _get_paginated_notices(request):
    """
    获取分页的通知列表
    """
    notices = _get_notices_with_read_status(request.user)
    paginator = Paginator(notices, 12)  # 每页12条
    page_number = request.GET.get('page')
    return paginator.get_page(page_number)


# @login_required
def notice_list(request):
    """
    通知列表视图: 只显示已发布的通知, 并标记用户已读状态, 最新的通知在前, 12条一页
    """
    page_obj = _get_paginated_notices(request)
    
    # 获取最新的通知ID（用于在模板中特殊显示）
    latest_notice_id = None
    if page_obj.object_list:
        latest_notice_id = page_obj.object_list[0].id if page_obj.number == 1 else None
    
    return render(request, 'notices/notice_list.html', {
        'page_obj': page_obj,
        'title': '通知列表',
        'latest_notice_id': latest_notice_id,
    })


# @login_required
def notice_list_partial(request):
    """
    部分通知列表视图: 用于HTMX自动刷新
    """
    page_obj = _get_paginated_notices(request)
    
    # 获取最新的通知ID（用于在模板中特殊显示）
    latest_notice_id = None
    if page_obj.object_list:
        latest_notice_id = page_obj.object_list[0].id if page_obj.number == 1 else None
    
    return render(request, 'notices/notice_list_partial.html', {
        'page_obj': page_obj,
        'latest_notice_id': latest_notice_id,
    })


# @login_required
def notice_detail(request, pk: int):
    """
    通知详情视图：显示通知的详细内容
    """
    notice = get_object_or_404(Notice.objects.prefetch_related('attachments'), pk=pk, is_published=True)
    
    return render(request, 'notices/notice_detail.html', {
        'notice': notice,
        'title': notice.title,
    })


# @login_required
@permission_required('notices.add_notice')
def notice_create(request):
    """
    创建通知视图：支持多附件上传
    """
    if request.method == 'POST':
        form = NoticeForm(request.POST, request.FILES)
        if form.is_valid():
            notice = form.save(commit=False)
            notice.published_by = request.user
            
            # 如果发布，设置发布时间
            if notice.is_published:
                notice.published_at = timezone.now()
            
            notice.save()
            form.save_m2m()  # 保存多对多关系
            
            # 处理多个附件上传
            attachments = form.cleaned_data.get('attachments', [])
            if attachments:
                # 如果attachments是单个文件，转换为列表
                if not isinstance(attachments, list):
                    attachments = [attachments]
                
                for file in attachments:
                    if file:
                        NoticeAttachment.objects.create(
                            notice=notice,
                            file=file
                        )
            
            messages.success(
                request, 
                f'通知已{"发布" if notice.is_published else "保存为草稿"}成功！'
            )
            return redirect('notices:notice_detail', pk=notice.pk)
    else:
        form = NoticeForm()
    
    return render(request, 'notices/notice_create.html', {
        'form': form,
        'title': '发布通知',
    })
