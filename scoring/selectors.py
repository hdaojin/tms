from django.db.models import Q

from .models import ScoringParticipant, ScoringResult


def scoring_participants_visible_to(user, queryset=None):
    queryset = queryset if queryset is not None else ScoringParticipant.objects.all()
    if user.has_perm("scoring.view_all_scoringparticipant"):
        return queryset
    return queryset.filter(Q(user=user) | Q(assessment_participant__user=user)).distinct()


def scoring_results_visible_to(user, queryset=None):
    queryset = queryset if queryset is not None else ScoringResult.objects.all()
    if user.has_perm("scoring.view_all_scoringresult"):
        return queryset
    return queryset.filter(Q(participant__user=user) | Q(participant__assessment_participant__user=user)).distinct()
