from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.db.models import Q

from .models import Notice


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


@login_required
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


@login_required
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


@login_required
def notice_detail(request, pk: int):
    """
    通知详情视图：显示通知的详细内容
    """
    notice = get_object_or_404(Notice.objects.prefetch_related('attachments'), pk=pk, is_published=True)
    
    # 检查用户是否有权限查看该通知
    user_group_ids = list(request.user.groups.values_list('id', flat=True))
    if notice.target_groups.exists():
        # 如果通知有目标组，检查用户是否在目标组中
        if not notice.target_groups.filter(id__in=user_group_ids).exists():
            # 用户不在目标组中，返回404
            return render(request, '404.html', status=404)
    
    return render(request, 'notices/notice_detail.html', {
        'notice': notice,
        'title': notice.title,
    })
