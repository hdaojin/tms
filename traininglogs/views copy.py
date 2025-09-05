from pathlib import Path
from datetime import date
import calendar

from django.shortcuts import render, redirect, get_object_or_404
from django.conf import settings
from django.contrib import messages
from django.core.files.base import ContentFile
from django.contrib.auth.models import User, Group
from django.db.models import Q
from django.utils import timezone
from django.http import FileResponse

from .forms import TrainingLogUploadForm
from .models import TrainingLog


# Create your views here.
def upload_training_log(request):
    if request.method == 'POST':
        form = TrainingLogUploadForm(request.POST, request.FILES)
        if form.is_valid():
            training_log = form.save(commit=False)
            training_log.uploaded_by = request.user

            # 获取上传的文件
            uploaded_file = request.FILES['upload']

            # 构建新的文件名，避免局部变量覆盖 datetime.date
            original_extension = uploaded_file.name.split('.')[-1]
            head = getattr(settings, 'WSCSKILL_NAME', '')
            date_str = training_log.training_date.strftime('%Y年%m月%d日')
            group_obj = request.user.groups.first()
            user_role = group_obj.name if group_obj else '未知角色'
            user_name = request.user.first_name or request.user.username
            new_filename = f"{head}{date_str}{user_role}日志-{user_name}.{original_extension}"

            # 设置数据库中的文件名字段
            training_log.filename = new_filename

            # 将文件内容读取到内存
            file_content = uploaded_file.read()

            # 保存上传文件（使用新文件名）
            training_log.upload.save(new_filename, ContentFile(file_content), save=False)

            # 保存模型实例
            training_log.save()
            # with open(Path(settings.LOGS_DIR) / Path(new_filename), 'wb+') as destination:
            #     for chunk in uploaded_file.chunks():
            #         destination.write(chunk)
            messages.success(request, '训练日志上传成功!')
            return redirect('traininglogs:list_training_logs')
    else:
        form = TrainingLogUploadForm()
    return render(request, 'traininglogs/upload_training_log.html', {'form': form, 'title': '上传训练日志'})


def training_logs(request):
    # 获取请求中的年份和月份参数，如果没有则使用当前年月
    selected_year = int(request.GET.get('year', timezone.now().year))
    selected_month = int(request.GET.get('month', timezone.now().month))
    
    # 创建所选月份的开始和结束日期
    start_date = date(selected_year, selected_month, 1)
    _, last_day = calendar.monthrange(selected_year, selected_month)
    end_date = date(selected_year, selected_month, last_day)
    
    # 过滤当前用户在选定月份范围内的训练日志
    training_logs = TrainingLog.objects.filter(
        uploaded_by=request.user,
        training_date__gte=start_date,
        training_date__lte=end_date
    ).order_by('-training_date')
    
    title = f'训练日志列表 - 我的日志 ({selected_year}年{selected_month}月)'
    
    # 准备月份选择器的数据，显示最近1年到当前月
    months = []
    current_date = timezone.now().date()
    
    # 从当前月开始，往前推12个月
    for i in range(13):  # 当前月份及往前12个月，共13个月
        # 计算年和月
        year = current_date.year
        month = current_date.month - i
        
        # 处理月份为负数的情况
        while month <= 0:
            month += 12
            year -= 1
            
        months.append({
            'year': year,
            'month': month,
            'name': f"{year}年{month}月"
        })
    
    # 按照时间排序，最新的月份在最前面
    months.sort(key=lambda x: (x['year'], x['month']), reverse=True)
    
    context = {
        'title': title,
        'training_logs': training_logs,
        'months': months,
        'selected_year': selected_year,
        'selected_month': selected_month,
    }
    
    return render(request, 'traininglogs/training_logs.html', context)


def view_training_log(request, log_id):
    try:
        training_log = get_object_or_404(TrainingLog, id=log_id)
        if training_log.uploaded_by == request.user:
            if training_log.upload and training_log.upload.path:
                file_path = Path(training_log.upload.path)
                if file_path.is_file():
                    response = FileResponse(open(file_path, 'rb'))
                    response['Content-Disposition'] = f'attachment; filename="{training_log.filename}"'
                    return response
                else:
                    messages.error(request, '文件不存在或已被删除!')
            else:
                messages.error(request, '没有上传文件或文件路径无效!')
        else:
            messages.error(request, '只能下载自己上传的训练日志!')
        return redirect('traininglogs:list_training_logs')
    except Exception as e:
        messages.error(request, f'下载日志时发生错误: {str(e)}')
        return redirect('traininglogs:list_training_logs')


def delete_training_log(request, log_id):
    training_log = get_object_or_404(TrainingLog, id=log_id)
    if training_log.uploaded_by == request.user:
        # 删除关联的物理文件
        if training_log.upload and training_log.upload.path:
            if Path(training_log.upload.path).is_file():
                Path(training_log.upload.path).unlink()
        
        # 删除数据库记录
        training_log.delete()
        messages.success(request, '训练日志删除成功!')
    else:
        messages.error(request, '只能删除自己上传的训练日志!')
    return redirect('traininglogs:list_training_logs')


def training_log_statistics(request):
    # 获取请求中的年份和月份参数，如果没有则使用当前年月
    selected_year = int(request.GET.get('year', timezone.now().year))
    selected_month = int(request.GET.get('month', timezone.now().month))
    
    # 创建所选月份的开始和结束日期
    start_date = date(selected_year, selected_month, 1)
    _, last_day = calendar.monthrange(selected_year, selected_month)
    # _，的作用是忽略返回的第一个值，计算该月份的最后一天
    
    # 如果是当前月份，则只统计到当前日期
    current_now = timezone.now().date()
    if selected_year == current_now.year and selected_month == current_now.month:
        end_date = current_now
    else:
        end_date = date(selected_year, selected_month, last_day)      
    
    # 获取所有需要提交日志的教练和选手（排除 profile.submission_training_log=False 的用户）
    # 获取教练：包括没有个人资料的或个人资料中submission_training_log=True的
    coaches = User.objects.filter(
        groups__name='教练',
        is_active=True,
    ).exclude(
        profile__submission_training_log=False
    ).distinct()
    coach_ids = set(coaches.values_list('id', flat=True))
    
    # 获取选手：包括没有个人资料的或个人资料中submission_training_log=True的
    competitors = User.objects.filter(
        groups__name='选手',
        is_active=True,
    ).exclude(
        profile__submission_training_log=False
    ).distinct()
    competitor_ids = set(competitors.values_list('id', flat=True))
    
    # 获取用户ID到用户对象的映射
    all_users = User.objects.filter(Q(id__in=coach_ids) | Q(id__in=competitor_ids))
    user_map = {user.pk: user for user in all_users}    # 获取该月份的所有有效日志提交情况
    logs = TrainingLog.objects.filter(
        training_date__gte=start_date,
        training_date__lte=end_date
    ).values('training_date', 'uploaded_by_id')
    
    # 创建日期到提交用户的映射
    date_to_users = {}
    for log in logs:
        log_date = log['training_date']
        user_id = log['uploaded_by_id']
        
        if log_date not in date_to_users:
            date_to_users[log_date] = set()
        date_to_users[log_date].add(user_id)
    
    # 按日期统计，只统计到当前日期或月末
    daily_stats = {}
    for day in range(1, end_date.day + 1):  # 如果是当前月，只统计到当前日期
        current_date = date(selected_year, selected_month, day)
        submitted_user_ids = date_to_users.get(current_date, set())
        
        # 获取已提交的教练
        submitted_coach_ids = coach_ids.intersection(submitted_user_ids)
        submitted_coaches = [user_map[uid] for uid in submitted_coach_ids if uid in user_map]
        
        # 获取已提交的选手
        submitted_competitor_ids = competitor_ids.intersection(submitted_user_ids)
        submitted_competitors = [user_map[uid] for uid in submitted_competitor_ids if uid in user_map]
        
        # 获取未提交的选手
        unsubmitted_competitor_ids = competitor_ids - submitted_user_ids
        unsubmitted_competitors = [user_map[uid] for uid in unsubmitted_competitor_ids if uid in user_map]
        
        # 获取未提交的教练
        unsubmitted_coach_ids = coach_ids - submitted_user_ids
        unsubmitted_coaches = [user_map[uid] for uid in unsubmitted_coach_ids if uid in user_map]
        
        # 添加是否为星期日的标记
        is_sunday = current_date.weekday() == 6  # Python中0是星期一，6是星期日
        
        daily_stats[current_date] = {
            'submitted_coaches': submitted_coaches,
            'submitted_competitors': submitted_competitors,
            'unsubmitted_competitors': unsubmitted_competitors,
            'unsubmitted_coaches': unsubmitted_coaches,
            'is_sunday': is_sunday,
        }
    
    # 准备月份选择器的数据，显示最近1年到当前月
    months = []
    current_date = timezone.now().date()
    
    # 从当前月开始，往前推12个月
    for i in range(13):  # 当前月份及往前12个月，共13个月
        # 计算年和月
        year = current_date.year
        month = current_date.month - i
        
        # 处理月份为负数的情况
        while month <= 0:
            month += 12
            year -= 1
            
        months.append({
            'year': year,
            'month': month,
            'name': f"{year}年{month}月"
        })
    
    # 按照时间排序，最新的月份在最前面
    months.sort(key=lambda x: (x['year'], x['month']), reverse=True)
      # 对日期进行排序
    sorted_daily_stats = dict(sorted(daily_stats.items()))
    
    context = {
        'title': f"{selected_year}年{selected_month}月训练日志统计",
        'daily_stats': sorted_daily_stats,
        'months': months,
        'selected_year': selected_year,
        'selected_month': selected_month,
    }
    
    return render(request, 'traininglogs/training_log_statistics.html', context)


def athlete_logs(request):
    # 判断用户是否为教练
    coach_group = Group.objects.filter(name='教练').first()
    if not coach_group or not request.user.groups.filter(name='教练').exists():
        messages.error(request, '您没有权限查看选手日志!')
        return redirect('traininglogs:list_training_logs')
    
    # 获取所有选手
    competitor_group = Group.objects.filter(name='选手').first()
    if competitor_group:
        competitors = User.objects.filter(groups__name='选手').order_by('first_name')
    else:
        competitors = []
    
    # 获取指定选手的日志，如果没有选择则获取所有选手的日志
    competitor_id = request.GET.get('competitor_id')
    
    if competitor_id and competitor_id.isdigit():
        try:
            selected_competitor = User.objects.get(id=competitor_id)
            training_logs = TrainingLog.objects.filter(uploaded_by=selected_competitor).order_by('-training_date')
            title = f'训练日志列表 - {selected_competitor.first_name}的日志'
        except User.DoesNotExist:
            messages.error(request, '选择的选手不存在!')
            if competitor_group:
                training_logs = TrainingLog.objects.filter(uploaded_by__groups__name='选手').order_by('-training_date')
            else:
                training_logs = TrainingLog.objects.none()
            title = '训练日志列表 - 所有选手日志'
    else:
        if competitor_group:
            training_logs = TrainingLog.objects.filter(uploaded_by__groups__name='选手').order_by('-training_date')
        else:
            training_logs = TrainingLog.objects.none()
        title = '训练日志列表 - 所有选手日志'
    
    context = {
        'title': title,
        'training_logs': training_logs,
        'competitors': competitors,
        'selected_competitor_id': int(competitor_id) if competitor_id and competitor_id.isdigit() else None,
    }
    
    return render(request, 'traininglogs/athlete_logs.html', context)


def counterpart_training_logs(request):
    """教练查看所有选手日志，选手查看所有教练日志（按月）。"""
    # 判定身份
    is_coach = request.user.groups.filter(name='教练').exists()
    is_competitor = request.user.groups.filter(name='选手').exists()

    if not (is_coach or is_competitor):
        messages.error(request, '您没有所属角色，无法查看对向角色日志。')
        return redirect('traininglogs:list_training_logs')

    # 选择对向角色 queryset
    if is_coach:
        target_qs = User.objects.filter(groups__name='选手')
        role_desc = '选手日志'
    elif is_competitor:
        target_qs = User.objects.filter(groups__name='教练')
        role_desc = '教练日志'
    else:
        messages.error(request, '您没有所属角色，无法查看对向角色日志。')
        return redirect('traininglogs:list_training_logs')


    # 获取年月参数
    selected_year = int(request.GET.get('year', timezone.now().year))
    selected_month = int(request.GET.get('month', timezone.now().month))

    start_date = date(selected_year, selected_month, 1)
    _, last_day = calendar.monthrange(selected_year, selected_month)
    end_date = date(selected_year, selected_month, last_day)

    training_logs = TrainingLog.objects.filter(
        uploaded_by__in=target_qs,
        training_date__gte=start_date,
        training_date__lte=end_date,
    ).order_by('-training_date')

    # 月份选择器（复用13个月逻辑）
    months = []
    current_date = timezone.now().date()
    for i in range(13):
        year = current_date.year
        month = current_date.month - i
        while month <= 0:
            month += 12
            year -= 1
        months.append({'year': year, 'month': month, 'name': f"{year}年{month}月"})
    months.sort(key=lambda x: (x['year'], x['month']), reverse=True)

    context = {
        'title': f'训练日志列表 - {role_desc} ({selected_year}年{selected_month}月)',
        'training_logs': training_logs,
        'months': months,
        'selected_year': selected_year,
        'selected_month': selected_month,
    }
    return render(request, 'traininglogs/training_logs.html', context)


