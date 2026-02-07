from django.urls import path
from . import views


app_name = 'conduct'

urlpatterns = [
    # 奖惩记录
    path('records/', views.ConductRecordListView.as_view(), name='record_list'),
    path('records/create/', views.ConductRecordCreateView.as_view(), name='record_create'),
    path('records/<int:pk>/', views.ConductRecordDetailView.as_view(), name='record_detail'),
    path('records/<int:pk>/update/', views.ConductRecordUpdateView.as_view(), name='record_update'),
    path('records/<int:pk>/delete/', views.ConductRecordDeleteView.as_view(), name='record_delete'),
    path('records/<int:pk>/review/', views.ConductRecordReviewView.as_view(), name='record_review'),
    
    # 奖惩汇总
    path('summary/', views.ConductSummaryListView.as_view(), name='summary_list'),
    path('students/<int:student_id>/', views.StudentConductDetailView.as_view(), name='student_detail'),
    
    # 我的奖惩
    path('my/', views.MyConductView.as_view(), name='my_conduct'),
]
