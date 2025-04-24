from pathlib import Path
from datetime import date
import calendar

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
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
            
            # 构建新的文件名
            original_extension = uploaded_file.name.split('.')[-1]
            head = settings.WSCSKILL_NAME
            date = training_log.training_date.strftime('%Y年%m月%d日')
            user_role = request.user.groups.first().name
            user_name = request.user.first_name
            new_filename = f"{head}{date}{user_role}日志-{user_name}.{original_extension}"
            
            # 设置数据库中的文件名字段
            training_log.filename = new_filename
            
            # 将文件内容读取到内存
            file_content = uploaded_file.read()
            
            # 清除之前的上传对象并创建一个新的，使用新文件名
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


@login_required
def training_logs(request):
    training_logs = TrainingLog.objects.filter(uploaded_by=request.user).order_by('-training_date')
    title = '训练日志列表 - 我的日志'
    return render(request, 'traininglogs/training_logs.html', {'title': title, 'training_logs': training_logs})


@login_required
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


@login_required
def delete_training_log(request, log_id):
    training_log = TrainingLog.objects.get(id=log_id)
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


@login_required
def training_log_statistics(request):
    # 获取请求中的月份参数，如果没有则使用当前月份
    selected_year = int(request.GET.get('year', timezone.now().year))
    selected_month = int(request.GET.get('month', timezone.now().month))
    
    # 创建所选月份的开始和结束日期
    start_date = date(selected_year, selected_month, 1)
    _, last_day = calendar.monthrange(selected_year, selected_month)
    end_date = date(selected_year, selected_month, last_day)
    
    # 获取所有教练和选手
    coaches = User.objects.filter(groups__name='教练').distinct()
    coach_ids = set(coaches.values_list('id', flat=True))
    
    players = User.objects.filter(groups__name='选手').distinct()
    player_ids = set(players.values_list('id', flat=True))
    
    # 获取用户ID到用户对象的映射
    all_users = User.objects.filter(Q(id__in=coach_ids) | Q(id__in=player_ids))
    user_map = {user.id: user for user in all_users}
    
    # 获取该月份的所有日志提交情况
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
    
    # 按日期统计
    daily_stats = {}
    for day in range(1, last_day + 1):
        current_date = date(selected_year, selected_month, day)
        submitted_user_ids = date_to_users.get(current_date, set())
        
        # 获取已提交的教练
        submitted_coach_ids = coach_ids.intersection(submitted_user_ids)
        submitted_coaches = [user_map[uid] for uid in submitted_coach_ids if uid in user_map]
        
        # 获取已提交的选手
        submitted_player_ids = player_ids.intersection(submitted_user_ids)
        submitted_players = [user_map[uid] for uid in submitted_player_ids if uid in user_map]
        
        # 获取未提交的选手
        unsubmitted_player_ids = player_ids - submitted_user_ids
        unsubmitted_players = [user_map[uid] for uid in unsubmitted_player_ids if uid in user_map]
        
        daily_stats[current_date] = {
            'submitted_coaches': submitted_coaches,
            'submitted_players': submitted_players,
            'unsubmitted_players': unsubmitted_players,
        }
    
    # 准备月份选择器的数据
    months = []
    current_year = timezone.now().year
    for year in range(current_year - 1, current_year +1):
        for month in range(1, 13):
            months.append({
                'year': year,
                'month': month,
                'name': f"{year}年{month}月"
            })
    
    context = {
        'title': f"{selected_year}年{selected_month}月训练日志统计",
        'daily_stats': daily_stats,
        'months': months,
        'selected_year': selected_year,
        'selected_month': selected_month,
    }
    
    return render(request, 'traininglogs/training_log_statistics.html', context)


@login_required
def athlete_logs(request):
    # 判断用户是否为教练
    coach_group = Group.objects.filter(name='教练').first()
    if not coach_group or not request.user.groups.filter(id=coach_group.id).exists():
        messages.error(request, '您没有权限查看选手日志!')
        return redirect('traininglogs:list_training_logs')
    
    # 获取所有选手
    player_group = Group.objects.filter(name='选手').first()
    if not player_group:
        players = []
    else:
        players = User.objects.filter(groups__id=player_group.id).order_by('first_name')
    
    # 获取指定选手的日志，如果没有选择则获取所有选手的日志
    player_id = request.GET.get('player_id')
    
    if player_id:
        try:
            selected_player = User.objects.get(id=player_id)
            training_logs = TrainingLog.objects.filter(uploaded_by=selected_player).order_by('-training_date')
            title = f'训练日志列表 - {selected_player.first_name}的日志'
        except User.DoesNotExist:
            messages.error(request, '选择的选手不存在!')
            training_logs = TrainingLog.objects.filter(uploaded_by__groups__id=player_group.id).order_by('-training_date')
            title = '训练日志列表 - 所有选手日志'
    else:
        training_logs = TrainingLog.objects.filter(uploaded_by__groups__id=player_group.id).order_by('-training_date')
        title = '训练日志列表 - 所有选手日志'
    
    context = {
        'title': title,
        'training_logs': training_logs,
        'players': players,
        'selected_player_id': int(player_id) if player_id and player_id.isdigit() else None,
    }
    
    return render(request, 'traininglogs/athlete_logs.html', context)


