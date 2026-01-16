from django.shortcuts import render, get_object_or_404
from django.db.models import Prefetch
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from .models import Assessment, Score, AssessmentModule

@login_required
def assessment_list(request):
    """
    显示考核列表
    - 普通用户：显示参与的考核及自己的成绩（当前+历史）
    - 有权限用户：显示所有考核列表，点击进入详情查看所有人成绩
    """
    today = timezone.now().date()
    
    # 假设权限名为 assessment.view_all_scores，如果没有定义，暂时用 is_staff
    can_view_all = request.user.is_superuser or request.user.has_perm('assessment.view_all_scores')

    if can_view_all:
        assessments = Assessment.objects.all().order_by('-start_date')
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
    # Upcoming: start_date > today (虽然需求没提，但加上更好)
    
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
            if hasattr(assessment, 'user_modules_info'):
                for am in assessment.user_modules_info:
                    # 排除包含 "English" 的模块 (大小写不敏感)
                    if 'english' not in am.module.name.lower():
                        if am.user_score:
                             my_total += am.user_score[0].score
            assessment.my_total_score = my_total
            
            # 2. 计算排名
            # 聚合该次考核所有参与者的总分（排除 English）
            # 获取该考核下排除 English 的 AssessmentModule ID 列表
            valid_am_ids = assessment.assessmentmodule_set.exclude(
                module__name__icontains='English'
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
def assessment_detail(request, pk):
    """
    管理员查看某次考核的所有人成绩
    """
    # 简单的权限检查，实际应用中最好用 @permission_required
    if not (request.user.is_staff or request.user.has_perm('assessment.view_all_scores')):
         return render(request, '403.html', status=403)

    assessment = get_object_or_404(Assessment, pk=pk)
    
    # 获取该考核的所有模块
    modules = assessment.assessmentmodule_set.select_related('module').all()
    
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
        score_map[(s.user_id, s.assessment_module_id)] = s
        
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
             score_obj = score_map.get((participant.id, am.id))
             
             val = score_obj.score if score_obj else 0
             row['scores'].append({
                 'module_id': am.id,
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
    sort_by = request.GET.get('sort', 'total') # 默认按 rank_score 排序 (其实是 total 里的 rank_score 逻辑)
    # 之前逻辑是按 rank_score 排序，这里默认值给 rank_score 或者 total 都可以，看前端传啥
    # 为了保持一致，默认走 rank_score 对应的逻辑
    
    direction = request.GET.get('dir', 'desc')
    reverse = (direction == 'desc')
    
    def get_sort_value(row):
        if sort_by == 'total':
            return row['rank_score'] # 只有 rank_score 才是真正用于排名的总分 (排除 English)
        elif sort_by.startswith('module_'):
            try:
                mod_id = int(sort_by.split('_')[1])
                for s in row['scores']:
                    if s['module_id'] == mod_id:
                        return s['val']
            except (ValueError, IndexError):
                pass
        return 0

    table_rows.sort(key=get_sort_value, reverse=reverse)

    # 计算排名 (始终基于 rank_score 计算，不受显示排序影响，或者如果按模块排序，排名是否重新计算？)
    # 通常排名字段是固定的（即总分排名），只是列表显示顺序变了。
    # 所以我们需要先按 rank_score 排算出 rank，然后再按用户选的字段重排。
    
    # 1. 先按排名的规则排序一次，计算 rank
    table_rows.sort(key=lambda x: x['rank_score'], reverse=True)
    current_rank = 1
    for i, row in enumerate(table_rows):
        if i > 0 and row['rank_score'] < table_rows[i-1]['rank_score']:
            current_rank = i + 1
        row['rank'] = current_rank
        
    # 2. 如果用户选择了其他排序方式，再排一次
    if sort_by != 'total' or direction != 'desc':
         table_rows.sort(key=get_sort_value, reverse=reverse)

    context = {
        'assessment': assessment,
        'modules': modules,
        'table_rows': table_rows, # 恢复使用 table_rows
        'title': f'考核详情 - {assessment.name}',
    }
    return render(request, 'assessment/assessment_detail.html', context)

