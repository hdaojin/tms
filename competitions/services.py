from __future__ import annotations

from .models import CompetitionPerson, CompetitionProjectMember, Member


def resolve_or_create_competition_person(
    *,
    person=None,
    new_person_name: str = '',
    new_person_organization: str = '',
    new_person_user=None,
):
    if person is not None:
        return person

    return CompetitionPerson.objects.create(
        name=new_person_name.strip(),
        organization=(new_person_organization or '').strip(),
        user=new_person_user,
    )


def create_or_link_competition_project_member(
    *,
    competition_project,
    existing_member=None,
    new_member_name: str = '',
    new_member_code: str = '',
    new_member_flag=None,
):
    if existing_member is not None:
        member = existing_member
    else:
        member = Member(
            name=new_member_name.strip(),
            code=new_member_code.strip(),
            level=competition_project.required_member_level,
            flag=new_member_flag,
        )
        member.full_clean()
        member.save()

    link, _created = CompetitionProjectMember.objects.get_or_create(
        competition_project=competition_project,
        member=member,
    )
    return link