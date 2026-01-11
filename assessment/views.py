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
    can_view_all = request.user.is_staff or request.user.has_perm('assessment.view_all_scores')

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
            
    context = {
        'can_view_all': can_view_all,
        'current_assessments': current_assessments,
        'past_assessments': past_assessments,
        'upcoming_assessments': upcoming_assessments,
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
         for am in modules: # 注意这里的 modules 其实是 AssessmentModule 列表
             # 我们用 AssessmentModule 的 id 来匹配 Score 中的 assessment_module_id
             score_obj = score_map.get((participant.id, am.id))
             
             row['scores'].append({
                 'module_id': am.id,
                 'val': score_obj.score if score_obj else 0, # 或者 '-'
                 'obj': score_obj
             })
             if score_obj:
                 total_score += score_obj.score
         
         row['total'] = total_score
         table_rows.append(row)

    context = {
        'assessment': assessment,
        'modules': modules,
        'table_rows': table_rows,
    }
    return render(request, 'assessment/assessment_detail.html', context)

