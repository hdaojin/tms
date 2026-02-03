from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Prefetch
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.utils import timezone
from core.constants import GROUP_COACH
from .models import Assessment, Score, AssessmentModule, AssessmentAttachment
from .forms import AssessmentFileUploadForm

@login_required
def assessment_list(request):
    """
    显示考核列表
    - 普通用户：显示参与的考核及自己的成绩（当前+历史）
    - 有权限用户：显示所有考核列表，点击进入详情查看所有人成绩
    """
    today = timezone.now().date()
    
    # 假设权限名为 assessment.view_all_scores，如果没有定义，暂时用 is_superuser
    can_view_all = request.user.is_superuser or request.user.has_perm('assessment.view_all_scores')

    if can_view_all:
        assessments = Assessment.objects.prefetch_related('assessmentmodule_set__module').order_by('-start_date')
    else:
        # 普通用户：预加载该用户在该次考核中的成绩
        # 我们不能直接 prefetch 'scores'，因为那样会拿到所有人的成绩（如果没有过滤）
        # 最好只获取该用户的 Score
        
        # 定义内层的 Prefetch，只获取当前用户的 Score
        user_scores_prefetch = Prefetch(
            'scores',
            queryset=Score.objects.filter(user=request.user),
            to_attr='user_score' # 这个属性会挂在 AssessmentModule 实例上，是一个 list
        )

        # 定义外层的 Prefetch，获取 AssessmentModule 并带上上面的 user_score
        modules_prefetch = Prefetch(
            'assessmentmodule_set',
            queryset=AssessmentModule.objects.select_related('module').prefetch_related(user_scores_prefetch),
            to_attr='user_modules_info' # 这个属性会挂在 Assessment 实例上
        )
        
        assessments = Assessment.objects.filter(
            participants=request.user
        ).prefetch_related(modules_prefetch).order_by('-start_date')

    # 分组：当前考核和历史考核
    # Current: start_date <= today <= end_date 
    # History: end_date < today
    # Upcoming: start_date > today 
    
    current_assessments = []
    past_assessments = []
    upcoming_assessments = []

    for assessment in assessments:
        if assessment.end_date < today:
            past_assessments.append(assessment)
        elif assessment.start_date > today:
            upcoming_assessments.append(assessment)
        else:
            current_assessments.append(assessment)
    
    # 为历史考核计算总分和排名（仅限普通用户视图，或管理员查看自己成绩时）
    if not can_view_all:
        from django.db.models import Sum
        
        for assessment in past_assessments:
            # 1. 计算个人总分（排除 English）
            my_total = 0
            my_grand_total = 0
            assessment.max_ranking_score = 0
            assessment.max_grand_total_score = 0

            if hasattr(assessment, 'user_modules_info'):
                for am in assessment.user_modules_info:
                    score_val = 0
                    if am.user_score:
                         score_val = am.user_score[0].score
                    
                    my_grand_total += score_val
                    assessment.max_grand_total_score += am.max_score
                    
                    # 排除包含 "English" 的模块 (大小写不敏感)
                    if 'english' not in am.module.name.lower():
                        my_total += score_val
                        assessment.max_ranking_score += am.max_score
            
            assessment.my_total_score = my_total
            assessment.my_grand_total_score = my_grand_total
            
            # 2. 计算排名
            # 聚合该次考核所有参与者的总分（排除 English）
            # 获取该考核下排除 English 的 AssessmentModule ID 列表
            valid_am_ids = assessment.assessmentmodule_set.exclude(
                module__name__icontains='english'
            ).values_list('id', flat=True)
            
            # 按用户分组求和
            # 注意: 只有有成绩记录的用户才会出现在这里。没成绩的默认不算或 0。
            rank_data = Score.objects.filter(
                assessment_module_id__in=valid_am_ids
            ).values('user').annotate(
                total=Sum('score')
            ).order_by('-total')
            
            # 查找当前用户的排名
            # 处理同分情况：简单处理，按分数列表的 index + 1
            # 例如：[100, 90, 90, 80]，用户分数为 90。
            # 遍历列表找到第一个匹配的分数 (或者直接找 user id)
            
            my_rank = '-'
            # 提取所有总分列表 (排好序的)
            scores_list = [d['total'] for d in rank_data]
            
            try:
                # 这种方式处理并列排名：100(1), 90(2), 90(2), 80(4) -> index+1
                # 只要 my_total 在列表中，index 就会返回第一个匹配项的索引
                if my_total in scores_list:
                    my_rank = scores_list.index(my_total) + 1
                else:
                    # 可能用户虽然是参与者，但没有任何 Score 记录 (总分为0且不在 rank_data 中)
                    # 如果 my_total 是 0，且 scores_list 包含 0 ? 
                    # 如果用户完全没成绩记录，Score表中没数据，sum 也不会出来。
                    # 此时 rank 不显示或显示为最后？
                    # 简单起见，如果没数据，显示 '-'
                    pass
            except ValueError:
                pass
                
            assessment.my_rank = my_rank

    context = {
        'can_view_all': can_view_all,
        'current_assessments': current_assessments,
        'past_assessments': past_assessments,
        'upcoming_assessments': upcoming_assessments,
        'title': '考核列表',
    }
    return render(request, 'assessment/assessment_list.html', context)


@login_required
@permission_required('assessment.view_all_scores', raise_exception=True)
def assessment_detail(request, pk):
    """
    管理员查看某次考核的所有人成绩
    """
    assessment = get_object_or_404(Assessment, pk=pk)
    
    # 获取该考核的所有模块（预取附件用于显示考核资料）
    modules = AssessmentModule.objects.select_related('module').prefetch_related('attachments').filter(assessment=assessment)
    
    # 获取该考核的所有参与者，并预加载他们的成绩
    # 结构：List of Users. Each User has map of Module -> Score
    participants = assessment.participants.all().order_by('username')
    
    # 为了在模板中方便遍历：行是用户，列是模块
    # 我们需要构建一个数据结构
    
    # 获取本次考核的所有相关成绩
    all_scores = Score.objects.filter(
        assessment_module__assessment=assessment
    ).select_related('user', 'assessment_module')
    
    # 构建 score_map: {(user_id, module_id): score_obj}
    score_map = {}
    for s in all_scores:
        # 注意这里 assessment_module 已经在 all_scores 中被 select_related 了
        # 但是我们要根据 module.pk 来对应列，所以要通过 assessment_module.module_id
        score_map[(s.user.pk, s.assessment_module.pk)] = s
        
    # 为每个 participant 构建 row_data
    table_rows = []
    for participant in participants:
         row = {
             'user': participant,
             'scores': []
         }
         total_score = 0
         rank_score = 0 # English 不计入总分用于排名
         
         for am in modules: # 注意这里的 modules 其实是 AssessmentModule 列表
             # 我们用 AssessmentModule 的 id 来匹配 Score 中的 assessment_module_id
             score_obj = score_map.get((participant.pk, am.pk))
             
             val = score_obj.score if score_obj else 0
             row['scores'].append({
                 'module_id': am.pk,
                 'val': val,
                 'obj': score_obj
             })
             if score_obj:
                 total_score += val
                 # 排除 English
                 if 'english' not in am.module.name.lower():
                     rank_score += val
         
         row['total'] = total_score
         row['rank_score'] = rank_score
         table_rows.append(row)

    # 排序处理
    # 优化：采用 sort=-total 这种格式，移除 redundant 的 dir 参数
    # 默认按 rank_score 降序 (-total)
    sort_param = request.GET.get('sort', '-total').strip()
    
    if sort_param.startswith('-'):
        sort_key = sort_param[1:]
        reverse = True
    else:
        sort_key = sort_param
        reverse = False
    
    def get_sort_value(row):
        if sort_key == 'total':
            return row['rank_score']
        elif sort_key == 'grand_total':
            return row['total']
        elif sort_key.startswith('module_'):
            try:
                mod_id = int(sort_key.split('_')[1])
                for s in row['scores']:
                    if s['module_id'] == mod_id:
                        return s['val']
            except (ValueError, IndexError):
                pass
        return 0

    # 1. 计算排名 (始终基于 rank_score 降序计算)
    # 先按 rank_score 降序排好，填入 rank
    table_rows.sort(key=lambda x: x['rank_score'], reverse=True)
    current_rank = 1
    for i, row in enumerate(table_rows):
        if i > 0 and row['rank_score'] < table_rows[i-1]['rank_score']:
            current_rank = i + 1
        row['rank'] = current_rank
        
    # 2. 应用显示排序
    # 如果显示排序就是默认的 -total，则不需要再次排序 (因为上面计算排名时已经排过了)
    if sort_param != '-total':
         table_rows.sort(key=get_sort_value, reverse=reverse)

    # 计算本次考核的满分
    max_ranking_score = 0 # 排名分满分（不含English）
    max_grand_total_score = 0 # 总分满分（含English）

    for am in modules:
        max_grand_total_score += am.max_score
        if 'english' not in am.module.name.lower():
            max_ranking_score += am.max_score

    context = {
        'assessment': assessment,
        'modules': modules,
        'table_rows': table_rows,
        'title': f'考核详情 - {assessment.name}',
        'current_sort': sort_param,
        'max_ranking_score': max_ranking_score,
        'max_grand_total_score': max_grand_total_score,
    }
    return render(request, 'assessment/assessment_detail.html', context)


@login_required
def assessment_file_upload(request, module_id):
    """
    考核资料上传页面
    针对特定的考核模块上传各种资料
    只有教练有权限访问
    """
    # 检查是否是教练
    if not request.user.groups.filter(name=GROUP_COACH).exists():
        messages.error(request, "只有教练可以上传考核资料")
        return redirect('assessment:list')
    
    assessment_module = get_object_or_404(
        AssessmentModule.objects.select_related('assessment', 'module'),
        pk=module_id
    )
    
    # 检查考核是否已结束
    today = timezone.now().date()
    if assessment_module.assessment.end_date < today:
        messages.warning(request, "该考核已结束，无法上传资料")
        return redirect('assessment:detail', pk=assessment_module.assessment.pk)
    
    if request.method == 'POST':
        form = AssessmentFileUploadForm(request.POST, request.FILES, instance=assessment_module)
        
        if form.is_valid():
            # 保存主表单
            form.save()
            
            # 处理多个附件文件
            attachment_files = request.FILES.getlist('attachments')
            if attachment_files:
                for file in attachment_files:
                    AssessmentAttachment.objects.create(
                        assessment_module=assessment_module,
                        file=file
                    )
            
            messages.success(request, f"已成功保存 {assessment_module.module.name} 的考核资料")
            return redirect('assessment:detail', pk=assessment_module.assessment.pk)
    else:
        form = AssessmentFileUploadForm(instance=assessment_module)
    
    # 获取已有附件
    existing_attachments = assessment_module.attachments.all()
    
    context = {
        'assessment_module': assessment_module,
        'form': form,
        'existing_attachments': existing_attachments,
        'title': f'{assessment_module.assessment.name} - {assessment_module.module.name} 资料上传',
        'title_icon': 'icon-[tabler--file-upload]',
    }
    return render(request, 'assessment/file_upload.html', context)


@login_required
def delete_module_file(request, module_id, field_name):
    """
    删除考核模块的单个文件（试题、评分标准、评分表、评分脚本）
    """
    # 检查是否是教练
    if not request.user.groups.filter(name=GROUP_COACH).exists():
        messages.error(request, "只有教练可以删除考核资料")
        return redirect('assessment:list')
    
    assessment_module = get_object_or_404(AssessmentModule, pk=module_id)
    
    # 检查考核是否已结束
    today = timezone.now().date()
    if assessment_module.assessment.end_date < today:
        messages.warning(request, "该考核已结束，无法删除资料")
        return redirect('assessment:detail', pk=assessment_module.assessment.pk)
    
    # 允许的字段名及其对应的标签和 accept 类型
    field_config = {
        'question_file': {
            'label': '试题文件',
            'accept': '.pdf,.doc,.docx,.xls,.xlsx,.zip',
            'required': False,
            'help_text': '上传试题文件',
        },
        'scoring_standard_file': {
            'label': '评分标准文件',
            'accept': '.pdf,.doc,.docx,.xls,.xlsx',
            'required': False,
            'help_text': '上传评分标准文件',
        },
        'scoring_sheet_file': {
            'label': '评分表文件',
            'accept': '.pdf,.xls,.xlsx',
            'required': False,
            'help_text': '上传评分表文件（非必须）',
        },
        'scoring_script_file': {
            'label': '评分脚本文件',
            'accept': '.py,.sh,.zip',
            'required': False,
            'help_text': '上传评分脚本文件（非必须）',
        },
    }
    
    if field_name not in field_config:
        messages.error(request, "无效的文件字段")
        return redirect('assessment:file_upload', module_id=module_id)
    
    # 删除文件
    file_field = getattr(assessment_module, field_name)
    if file_field:
        file_field.delete(save=True)
        messages.success(request, "文件已删除")
    
    # 如果是 HTMX 请求，返回上传组件的 HTML
    if request.headers.get('HX-Request'):
        config = field_config[field_name]
        from django.template.loader import render_to_string
        html = render_to_string('assessment/partials/file_uploader_wrapper.html', {
            'name': field_name,
            'accept': config['accept'],
            'required': config['required'],
            'label': config['label'],
            'help_text': config['help_text'],
            'field_name': field_name,
        })
        from django.http import HttpResponse
        return HttpResponse(html)
    
    return redirect('assessment:file_upload', module_id=module_id)


@login_required
def delete_attachment(request, attachment_id):
    """
    删除考核模块附件
    """
    # 检查是否是教练
    if not request.user.groups.filter(name=GROUP_COACH).exists():
        messages.error(request, "只有教练可以删除附件")
        return redirect('assessment:list')
    
    attachment = get_object_or_404(AssessmentAttachment, pk=attachment_id)
    module_id = attachment.assessment_module_id
    
    # 检查考核是否已结束
    today = timezone.now().date()
    if attachment.assessment_module.assessment.end_date < today:
        messages.warning(request, "该考核已结束，无法删除附件")
        return redirect('assessment:detail', pk=attachment.assessment_module.assessment.pk)
    
    # 删除附件（文件会通过信号自动清理）
    attachment.delete()
    messages.success(request, "附件已删除")
    
    # 如果是 HTMX 请求，返回空内容
    if request.headers.get('HX-Request'):
        from django.http import HttpResponse
        return HttpResponse('')
    
    return redirect('assessment:file_upload', module_id=module_id)

