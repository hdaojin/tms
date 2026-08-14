from django.urls import path

from .views import (
    ConductRecordCreateView,
    ConductRecordListView,
    ConductSummaryListView,
    conduct_attachment_view,
    item_choices_view,
    severity_choices_view,
)

app_name = 'behaviors'

urlpatterns = [
    path('', ConductRecordListView.as_view(), name='conductrecord_list'),
    path('summary/', ConductSummaryListView.as_view(), name='conductsummary_list'),
    path('create/', ConductRecordCreateView.as_view(), name='conductrecord_create'),
    path('<int:pk>/attachment/', conduct_attachment_view, name='conduct_attachment'),
    path('item-choices/', item_choices_view, name='item_choices'),
    path('severity-choices/', severity_choices_view, name='severity_choices'),
]
