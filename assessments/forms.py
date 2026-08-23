from django import forms
from django.contrib.auth import get_user_model
from django.db import transaction
from core.uploads import ASSESSMENT_DOCUMENT_UPLOAD_SPEC
from core.utils.forms import StyledFormMixin
from standards.forms import DefaultSkillProjectFormMixin
from standards.models import TechnicalDomain
from .models import (
    Assessment,
    AssessmentDocument,
    AssessmentModule,
    AssessmentModuleCoach,
    AssessmentModuleDomain,
    AssessmentParticipant,
)

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
            "status",
        ]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
            "description": forms.Textarea(attrs={"rows": 4}),
        }


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
            "duration_minutes",
            "counts_towards_ranking",
        ]
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        assessment = self.initial.get("assessment") or getattr(self.instance, "assessment", None)
        if self.is_bound and self.data.get("assessment"):
            assessment = (
                Assessment.objects.filter(pk=self.data.get("assessment")).select_related("skill_project").first()
            )
        if assessment:
            domains = TechnicalDomain.objects.filter(skill_project=assessment.skill_project, is_active=True)
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
        fields = ["assessment", "user", "external_code", "display_name", "role", "organization", "metadata"]


class AssessmentDocumentForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = AssessmentDocument
        fields = ["assessment", "module", "document_type", "title", "description", "file", "version"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["file"].widget.attrs.update(ASSESSMENT_DOCUMENT_UPLOAD_SPEC.widget_attrs())

    def clean(self):
        cleaned = super().clean()
        if (
            cleaned.get("assessment")
            and cleaned.get("module")
            and cleaned["module"].assessment_id != cleaned["assessment"].pk
        ):
            self.add_error("module", "评测模块必须属于当前竞赛与考核。")
        return cleaned
