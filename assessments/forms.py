from django import forms
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.forms import inlineformset_factory

from accounts.services.users import get_user_display_name
from core.uploads import ASSESSMENT_DOCUMENT_UPLOAD_SPEC
from core.utils.forms import StyledFormMixin
from standards.forms import DefaultSkillProjectFormMixin
from standards.models import TechnicalDomain
from standards.selectors import scoped_domains_for
from .models import (
    Assessment,
    AssessmentDocument,
    AssessmentAward,
    AssessmentFinalResult,
    AssessmentFinalScore,
    AssessmentModule,
    AssessmentModuleCoach,
    AssessmentModuleDomain,
    AssessmentParticipant,
    AssessmentType,
    CompetitionPerson,
    CompetitionRole,
)
from .selectors import assessment_modules_in_scope_for, assessments_in_scope_for

User = get_user_model()


class AssessmentForm(DefaultSkillProjectFormMixin, StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Assessment
        fields = [
            "skill_project",
            "series",
            "level",
            "training_cycle",
            "assessment_type",
            "name",
            "code",
            "start_date",
            "end_date",
            "location",
            "description",
        ]
        widgets = {
            "start_date": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "end_date": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "description": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        querysets = {
            "assessment_type": AssessmentType.objects.filter(is_active=True),
            "series": self.fields["series"].queryset.filter(is_active=True),
            "level": self.fields["level"].queryset.filter(is_active=True),
        }
        if self.instance.pk:
            querysets["assessment_type"] = AssessmentType.objects.filter(
                Q(is_active=True) | Q(pk=self.instance.assessment_type_id)
            )
            querysets["series"] = self.fields["series"].queryset.model.objects.filter(
                Q(is_active=True) | Q(pk=self.instance.series_id)
            )
            querysets["level"] = self.fields["level"].queryset.model.objects.filter(
                Q(is_active=True) | Q(pk=self.instance.level_id)
            )
        for field_name, queryset in querysets.items():
            self.fields[field_name].queryset = queryset.distinct()


class AssessmentUpdateForm(AssessmentForm):
    class Meta(AssessmentForm.Meta):
        fields = [
            "skill_project",
            "series",
            "level",
            "training_cycle",
            "assessment_type",
            "status",
            "name",
            "code",
            "start_date",
            "end_date",
            "location",
            "description",
        ]


class CompetitionPersonForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = CompetitionPerson
        fields = [
            "name",
            "organization",
            "country_or_region",
            "title",
            "email",
            "phone",
            "notes",
            "metadata",
            "is_active",
        ]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3}),
            "metadata": forms.Textarea(attrs={"rows": 3}),
        }


class CompetitionRoleForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = CompetitionRole
        fields = ["code", "name", "category", "description", "order", "is_active"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["code"].disabled = True


class AssessmentModuleForm(StyledFormMixin, forms.ModelForm):
    domains = forms.ModelMultipleChoiceField(
        label="技术领域", queryset=TechnicalDomain.objects.none(), widget=forms.CheckboxSelectMultiple
    )
    primary_domain = forms.ModelChoiceField(
        label="主要技术领域", queryset=TechnicalDomain.objects.none(), required=False
    )
    coaches = forms.ModelMultipleChoiceField(
        label="负责教练", queryset=User.objects.all(), required=False, widget=forms.CheckboxSelectMultiple
    )
    primary_coach = forms.ModelChoiceField(label="主教练", queryset=User.objects.all(), required=False)

    class Meta:
        model = AssessmentModule
        fields = [
            "assessment",
            "code",
            "name",
            "description",
            "order",
            "total_mark",
            "scheduled_start_at",
            "duration_minutes",
            "counts_towards_ranking",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "scheduled_start_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }

    def __init__(self, *args, user=None, permission="assessments.change_assessmentmodule", **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.permission = permission
        assessment_queryset = Assessment.objects.all()
        if user is not None:
            assessment_queryset = assessments_in_scope_for(user, permission)
            self.fields["assessment"].queryset = assessment_queryset

        assessment = self.initial.get("assessment") or getattr(self.instance, "assessment", None)
        if self.is_bound and self.data.get("assessment"):
            assessment = self.data.get("assessment")
        if assessment and not isinstance(assessment, Assessment):
            try:
                assessment = assessment_queryset.select_related("skill_project").get(pk=assessment)
            except (Assessment.DoesNotExist, TypeError, ValueError):
                assessment = None
        if assessment:
            domains = TechnicalDomain.objects.filter(skill_project=assessment.skill_project, is_active=True)
            has_project_scope = user is None or user.is_superuser or user.has_perm("assessments.change_all_assessment")
            is_assessment_owner = user is not None and assessment.created_by_id == user.pk
            is_explicit_coach = (
                user is not None and self.instance.pk and self.instance.coach_assignments.filter(user=user).exists()
            )
            if not has_project_scope and not is_assessment_owner and not is_explicit_coach:
                domains = domains.filter(pk__in=scoped_domains_for(user, permission).values("pk"))
            self.fields["domains"].queryset = domains
            self.fields["primary_domain"].queryset = domains
        if self.instance.pk:
            self.fields["domains"].initial = self.instance.domain_mappings.values_list("technical_domain_id", flat=True)
            self.fields["primary_domain"].initial = (
                self.instance.domain_mappings.filter(role=AssessmentModuleDomain.Role.PRIMARY)
                .values_list("technical_domain_id", flat=True)
                .first()
            )
            self.fields["coaches"].initial = self.instance.coach_assignments.values_list("user_id", flat=True)
            self.fields["primary_coach"].initial = (
                self.instance.coach_assignments.filter(role=AssessmentModuleCoach.Role.PRIMARY)
                .values_list("user_id", flat=True)
                .first()
            )

    def clean(self):
        cleaned = super().clean()
        domains, coaches = set(cleaned.get("domains") or []), set(cleaned.get("coaches") or [])
        if cleaned.get("primary_domain") and cleaned["primary_domain"] not in domains:
            self.add_error("primary_domain", "主要技术领域必须包含在技术领域中。")
        if cleaned.get("primary_coach") and cleaned["primary_coach"] not in coaches:
            self.add_error("primary_coach", "主教练必须包含在负责教练中。")
        return cleaned

    @transaction.atomic
    def save(self, commit=True):
        module = super().save(commit=commit)
        if not commit:
            return module
        module.domain_mappings.all().delete()
        for domain in self.cleaned_data["domains"]:
            AssessmentModuleDomain.objects.create(
                assessment_module=module,
                technical_domain=domain,
                role=AssessmentModuleDomain.Role.PRIMARY
                if domain == self.cleaned_data.get("primary_domain")
                else AssessmentModuleDomain.Role.RELATED,
            )
        module.coach_assignments.all().delete()
        for coach in self.cleaned_data.get("coaches") or []:
            AssessmentModuleCoach.objects.create(
                assessment_module=module,
                user=coach,
                role=AssessmentModuleCoach.Role.PRIMARY
                if coach == self.cleaned_data.get("primary_coach")
                else AssessmentModuleCoach.Role.COLLABORATOR,
            )
        return module


class AssessmentParticipantForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = AssessmentParticipant
        fields = [
            "assessment",
            "user",
            "competition_person",
            "role",
            "external_code",
            "display_name",
            "organization",
            "country_or_region",
            "metadata",
        ]

    def __init__(self, *args, user=None, permission="assessments.add_assessmentparticipant", **kwargs):
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields["assessment"].queryset = assessments_in_scope_for(user, permission)
        self.fields["display_name"].required = False
        roles = CompetitionRole.objects.filter(is_active=True)
        people = CompetitionPerson.objects.filter(is_active=True)
        if self.instance.role_id:
            roles = CompetitionRole.objects.filter(pk=self.instance.role_id) | roles
        if self.instance.competition_person_id:
            people = CompetitionPerson.objects.filter(pk=self.instance.competition_person_id) | people
        self.fields["role"].queryset = roles.distinct()
        self.fields["competition_person"].queryset = people.distinct()

    def clean(self):
        cleaned = super().clean()
        user = cleaned.get("user")
        competition_person = cleaned.get("competition_person")
        if user and competition_person:
            raise forms.ValidationError("参与人员不能同时关联系统用户和长期赛事人员。")

        display_name = (cleaned.get("display_name") or "").strip()
        if not display_name:
            if competition_person:
                display_name = competition_person.name
            elif user:
                display_name = get_user_display_name(user)
            else:
                display_name = (cleaned.get("external_code") or "").strip()
        if not display_name:
            self.add_error("display_name", "参与人员必须有显示名称。")
        cleaned["display_name"] = display_name

        if competition_person:
            cleaned["organization"] = cleaned.get("organization") or competition_person.organization
            cleaned["country_or_region"] = cleaned.get("country_or_region") or competition_person.country_or_region
        return cleaned


class AssessmentDocumentForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = AssessmentDocument
        fields = ["assessment", "module", "document_type", "title", "description", "file", "version"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, user=None, permission="assessments.add_assessmentdocument", **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.permission = permission
        if user is not None:
            modules = assessment_modules_in_scope_for(user, permission)
            if user.is_superuser or user.has_perm("assessments.change_all_assessment"):
                general_assessments = Assessment.objects.all()
            else:
                general_assessments = Assessment.objects.filter(created_by=user)
            assessments = Assessment.objects.filter(
                Q(pk__in=general_assessments.values("pk")) | Q(modules__in=modules)
            ).distinct()
            self.fields["assessment"].queryset = assessments
            self.fields["module"].queryset = modules.filter(assessment__in=assessments)
        self.fields["file"].widget.attrs.update(ASSESSMENT_DOCUMENT_UPLOAD_SPEC.widget_attrs())

    def clean(self):
        cleaned = super().clean()
        if (
            cleaned.get("assessment")
            and cleaned.get("module")
            and cleaned["module"].assessment_id != cleaned["assessment"].pk
        ):
            self.add_error("module", "评测模块必须属于当前竞赛与考核。")
        if self.user is not None and cleaned.get("assessment"):
            module = cleaned.get("module")
            if module is not None:
                if not assessment_modules_in_scope_for(
                    self.user,
                    self.permission,
                    AssessmentModule.objects.filter(pk=module.pk),
                ).exists():
                    self.add_error("module", "您无权管理该评测模块的资料。")
            elif not (
                self.user.is_superuser
                or self.user.has_perm("assessments.change_all_assessment")
                or cleaned["assessment"].created_by_id == self.user.pk
            ):
                self.add_error("assessment", "只有评测负责人可以上传整场通用资料。")
        return cleaned


class AssessmentFinalResultForm(StyledFormMixin, forms.ModelForm):
    awards = forms.ModelMultipleChoiceField(
        label="奖项",
        queryset=AssessmentAward.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = AssessmentFinalResult
        fields = ["rank", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["awards"].queryset = self.instance.participant.assessment.awards.all()
            self.fields["awards"].initial = self.instance.awards.all()


class AssessmentFinalScoreForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = AssessmentFinalScore
        fields = ["score_type", "label", "value", "max_value", "order"]


AssessmentFinalScoreFormSet = inlineformset_factory(
    AssessmentFinalResult,
    AssessmentFinalScore,
    form=AssessmentFinalScoreForm,
    extra=1,
    can_delete=True,
)


class AssessmentAwardForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = AssessmentAward
        fields = ["code", "name", "category", "description", "order"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}
