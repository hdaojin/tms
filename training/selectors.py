from __future__ import annotations

from .models import TrainingLog


def training_logs_visible_to(user, queryset=None):
    queryset = queryset if queryset is not None else TrainingLog.objects.all()
    if user.has_perm("training.view_all_traininglog"):
        return queryset
    return queryset.filter(uploaded_by=user)


def training_logs_changeable_by(user, queryset=None):
    queryset = queryset if queryset is not None else TrainingLog.objects.all()
    if user.has_perm("training.change_all_traininglog"):
        return queryset
    return queryset.filter(uploaded_by=user)
