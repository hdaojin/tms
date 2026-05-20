from __future__ import annotations

from django.db.models import Count
from django.db.models import Q

from accounts.services.users import get_user_display_name
from curriculum.models import ModuleAxis, StandardModule

from .models import (
    CompetitionPerson,
    CompetitionProject,
    CompetitionResult,
    Competitor,
    CompetitorUser,
    Member,
)


def get_competition_project_queryset():
    return CompetitionProject.objects.select_related(
        'competition__competition_type',
        'project',
    ).order_by('-competition__start_date', 'competition__name', 'project__name')


def get_competition_projects_for_competition(competition):
    return competition.competition_projects.select_related(
        'project',
    ).annotate(
        official_module_total=Count('competition_modules', distinct=True),
        competitor_total=Count('competitors', distinct=True),
        expert_total=Count('experts', distinct=True),
        result_total=Count('competitors__results', distinct=True),
    ).order_by('project__name')


def get_members_for_competition_project(competition_project, include_member=None):
    queryset = Member.objects.order_by('level', 'name')
    if competition_project is None or not getattr(competition_project, 'pk', None):
        return queryset.none()

    filters = Q(competition_project_links__competition_project=competition_project)
    if include_member is not None and getattr(include_member, 'pk', None):
        filters |= Q(pk=include_member.pk)
    return queryset.filter(filters).distinct()


def get_available_members_for_competition_project(competition_project, include_member=None):
    queryset = Member.objects.order_by('level', 'name')
    if competition_project is None or not getattr(competition_project, 'pk', None):
        return queryset.none()

    required_level = competition_project.required_member_level
    if required_level is None:
        return queryset.none()

    filters = Q(level=required_level) & (~Q(competition_project_links__competition_project=competition_project))
    if include_member is not None and getattr(include_member, 'pk', None):
        filters |= Q(pk=include_member.pk)
    return queryset.filter(filters).distinct().order_by('level', 'name')


def get_competitor_user_queryset():
    return CompetitorUser.objects.order_by('last_name', 'first_name', 'username')


def get_competition_person_queryset():
    return CompetitionPerson.objects.select_related('user').order_by('name', 'organization', 'pk')


def get_available_competition_people_for_competition_project(competition_project, include_person=None):
    queryset = get_competition_person_queryset()
    if competition_project is None or not getattr(competition_project, 'pk', None):
        return queryset.none()

    queryset = queryset.exclude(competitor_assignments__competition_project=competition_project)
    if include_person is not None and getattr(include_person, 'pk', None):
        queryset = (
            queryset | CompetitionPerson.objects.filter(pk=include_person.pk).select_related('user')
        ).distinct()
    return queryset.order_by('name', 'organization', 'pk')


def get_available_competitors_for_competition_project(competition_project, include_competitor=None):
    queryset = Competitor.objects.select_related(
        'member',
        'person__user',
        'competition_project__competition',
        'competition_project__project',
    )
    if competition_project is None:
        return queryset.none()

    queryset = queryset.filter(competition_project=competition_project)
    if include_competitor is not None and include_competitor.pk:
        return queryset.filter(Q(results__isnull=True) | Q(pk=include_competitor.pk)).distinct().order_by(
            'person__name',
            'pk',
        )
    return queryset.filter(results__isnull=True).order_by('person__name', 'pk')


def format_standard_module_label(module):
    return f'{module.code} - {module.name} [{module.module_set.name}]'


def format_module_axis_label(module_axis):
    return f'{module_axis.code} - {module_axis.name}'


def format_member_label(member):
    return f'{member.name} [{member.get_level_display()}]'


def format_competition_project_label(competition_project):
    return f'{competition_project.competition.name} / {competition_project.project.name}'


def format_competition_person_label(person):
    parts = [person.name]
    if person.organization:
        parts.append(person.organization)
    if person.user_id:
        parts.append(get_user_display_name(person.user))
    return ' / '.join(parts)


def format_competitor_label(competitor):
    return f'{competitor.name} / {competitor.member.name}'


def get_project_module_queryset(project):
    if project is None:
        return StandardModule.objects.none()
    return StandardModule.objects.filter(project=project).select_related('project', 'module_set').order_by(
        '-module_set__is_current',
        'module_set__sort_order',
        'sort_order',
        'code',
        'name',
    )


def get_project_module_axis_queryset(project):
    if project is None:
        return ModuleAxis.objects.none()
    return ModuleAxis.objects.filter(project=project).order_by('sort_order', 'code', 'name')


def get_competition_project_official_modules_queryset(competition_project):
    return competition_project.competition_modules.all().order_by('sort_order', 'code', 'pk')


def get_competition_project_competitors_queryset(competition_project):
    return competition_project.competitors.select_related('person__user', 'member').all().order_by('person__name', 'pk')


def get_competition_project_experts_queryset(competition_project):
    return competition_project.experts.select_related('person__user', 'member').all().order_by('person__name')


def get_competition_project_skill_positions_queryset(competition_project):
    return competition_project.skill_positions.select_related('person__user').all().order_by('position_name', 'person__name')


def get_competition_project_results_queryset(competition_project):
    return CompetitionResult.objects.filter(
        competitor__competition_project=competition_project,
    ).select_related(
        'competitor__member',
        'competitor__person__user',
    ).order_by('rank', '-score_700', 'competitor__person__name')