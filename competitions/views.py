from django.contrib.auth.decorators import login_required
from django.shortcuts import render

# from .models import ExamScore


# @login_required
# def my_scores(request):
#     qs = ExamScore.objects.filter(user=request.user).select_related('examination', 'model').order_by('-examination__date', 'module__code')
#     return render(request, 'competitions/my_scores.html', {
#         'title': '我的考试成绩',
#         'title_icon': 'icon-[tabler--trophy]',
#         'scores': qs
#     })
