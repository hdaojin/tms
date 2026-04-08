from django.urls import path

from .views import (
    ConductRecordCreateView,
    ConductRecordListView,
    ConductSummaryListView,
    item_choices_view,
    severity_choices_view,
)

app_name = 'conduct'

urlpatterns = [
    path('list/', ConductRecordListView.as_view(), name='conductrecord_list'),
    path('summary/', ConductSummaryListView.as_view(), name='conductsummary_list'),
    path('create/', ConductRecordCreateView.as_view(), name='conductrecord_create'),
    path('item-choices/', item_choices_view, name='item_choices'),
    path('severity-choices/', severity_choices_view, name='severity_choices'),
]
