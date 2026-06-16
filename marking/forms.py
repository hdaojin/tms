from django import forms
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db.models import Q

from assessments.models import AssessmentModule
from competitions.models import CompetitionModule
from core.uploads import MARKING_RESULT_PACKAGE_UPLOAD_SPEC, MARKING_WORKBOOK_UPLOAD_SPEC
from core.utils.forms import StyledFormMixin
from skilltrees.models import SkillNode

from .models import MarkingAspectSkillNodeMap, MarkingScheme
from .parser import WorkbookParseError, parse_marking_workbook
from .services import create_scheme_from_upload, import_result_package, validate_scheme_target


TARGET_COMPETITION_MODULE = "competition_module"
TARGET_ASSESSMENT_MODULE = "assessment_module"


def filter_scheme_queryset_for_user(queryset, user):
    if not user or not getattr(user, "is_authenticated", False):
        return queryset.none()
    if user.is_superuser:
        return queryset

    competition_module_type = ContentType.objects.get_for_model(CompetitionModule, for_concrete_model=False)
    assessment_module_type = ContentType.objects.get_for_model(AssessmentModule, for_concrete_model=False)

    allowed_assessment_modules = AssessmentModule.objects.all()
    if not user.has_perm("assessments.view_all_scores"):
        allowed_assessment_modules = allowed_assessment_modules.filter(
            Q(responsible_coach=user) | Q(assessment__participants=user)
        )

    return queryset.filter(
        Q(target_content_type=competition_module_type)
        | Q(
            target_content_type=assessment_module_type,
            target_object_id__in=allowed_assessment_modules.values("pk"),
        )
    )


class MarkingSchemeImportForm(StyledFormMixin, forms.Form):
    target_type = forms.ChoiceField(
        label="绑定类型",
        choices=(
            (TARGET_COMPETITION_MODULE, "竞赛官方模块"),
            (TARGET_ASSESSMENT_MODULE, "考核模块"),
        ),
    )
    competition_module = forms.ModelChoiceField(
        label="竞赛官方模块",
        queryset=CompetitionModule.objects.none(),
        required=False,
    )
    assessment_module = forms.ModelChoiceField(
        label="考核模块",
        queryset=AssessmentModule.objects.none(),
        required=False,
    )
    file = forms.FileField(
        label="评分表文件",
        help_text=MARKING_WORKBOOK_UPLOAD_SPEC.help_text("上传新版单模块评分表"),
        widget=forms.FileInput(attrs=MARKING_WORKBOOK_UPLOAD_SPEC.widget_attrs()),
    )

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        self.parsed_workbook = None
        self.target_object = None
        competition_modules = CompetitionModule.objects.select_related(
            "competition_project__competition",
            "competition_project__project",
        ).order_by(
            "-competition_project__competition__start_date",
            "competition_project__competition__name",
            "competition_project__project__name",
            "sort_order",
            "code",
        )
        if not self._can_manage_competition_modules():
            competition_modules = competition_modules.none()
        self.fields["competition_module"].queryset = competition_modules
        self.fields["competition_module"].label_from_instance = (
            lambda obj: f"{obj.competition_project.competition.name} / {obj.competition_project.project.name} / {obj.code} - {obj.name}"
        )
        assessment_modules = AssessmentModule.objects.select_related(
            "assessment",
            "module",
        ).order_by("-assessment__start_date", "assessment__name", "sort_order", "module__code")
        if not self._can_manage_all_assessments():
            if self.user and getattr(self.user, "is_authenticated", False):
                assessment_modules = assessment_modules.filter(responsible_coach=self.user)
            else:
                assessment_modules = assessment_modules.none()
        self.fields["assessment_module"].queryset = assessment_modules
        self.fields["assessment_module"].label_from_instance = (
            lambda obj: f"{obj.assessment.name} / {obj.module.code} - {obj.module.name}"
        )

    def _can_manage_all_assessments(self):
        return bool(
            self.user
            and getattr(self.user, "is_authenticated", False)
            and (self.user.is_superuser or self.user.has_perm("assessments.view_all_scores"))
        )

    def _can_manage_competition_modules(self):
        return bool(
            self.user
            and getattr(self.user, "is_authenticated", False)
            and (
                self.user.is_superuser
                or self.user.has_perm("competitions.change_competitionmodule")
                or self.user.has_perm("competitions.add_competitionresult")
            )
        )

    def clean(self):
        cleaned_data = super().clean()
        target_type = cleaned_data.get("target_type")
        competition_module = cleaned_data.get("competition_module")
        assessment_module = cleaned_data.get("assessment_module")
        if target_type == TARGET_COMPETITION_MODULE:
            if competition_module is None:
                self.add_error("competition_module", "请选择竞赛官方模块。")
            self.target_object = competition_module
        elif target_type == TARGET_ASSESSMENT_MODULE:
            if assessment_module is None:
                self.add_error("assessment_module", "请选择考核模块。")
            self.target_object = assessment_module

        uploaded_file = cleaned_data.get("file")
        if uploaded_file is not None:
            try:
                MARKING_WORKBOOK_UPLOAD_SPEC.validate_file(uploaded_file)
                self.parsed_workbook = parse_marking_workbook(uploaded_file)
                if self.target_object is not None:
                    validate_scheme_target(self.target_object, self.parsed_workbook)
            except WorkbookParseError as exc:
                self.add_error("file", ValidationError(exc.errors))
            except ValidationError as exc:
                self.add_error("file", exc)
            finally:
                if hasattr(uploaded_file, "seek"):
                    uploaded_file.seek(0)
        return cleaned_data

    def save(self):
        return create_scheme_from_upload(
            uploaded_file=self.cleaned_data["file"],
            target=self.target_object,
            user=self.user,
        )


class MarkingResultImportForm(StyledFormMixin, forms.Form):
    scheme = forms.ModelChoiceField(label="评分方案", queryset=MarkingScheme.objects.none())
    file = forms.FileField(
        label="JSON 结果包",
        help_text=MARKING_RESULT_PACKAGE_UPLOAD_SPEC.help_text("上传 CMP 标准结果包"),
        widget=forms.FileInput(attrs=MARKING_RESULT_PACKAGE_UPLOAD_SPEC.widget_attrs()),
    )

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        scheme = kwargs.pop("scheme", None)
        super().__init__(*args, **kwargs)
        scheme_queryset = MarkingScheme.objects.select_related("standard_module").order_by(
            "-created_at",
            "module_code",
        )
        self.fields["scheme"].queryset = filter_scheme_queryset_for_user(scheme_queryset, self.user)
        if scheme is not None:
            self.fields["scheme"].initial = scheme
            self.fields["scheme"].widget = forms.HiddenInput()

    def clean_file(self):
        uploaded_file = self.cleaned_data["file"]
        MARKING_RESULT_PACKAGE_UPLOAD_SPEC.validate_file(uploaded_file)
        return uploaded_file

    def save(self):
        return import_result_package(
            scheme=self.cleaned_data["scheme"],
            uploaded_file=self.cleaned_data["file"],
            user=self.user,
        )


class MarkingAspectSkillNodeMapForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = MarkingAspectSkillNodeMap
        fields = ["skill_node", "is_primary", "weight", "note"]
        widgets = {
            "note": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, aspect, **kwargs):
        self.aspect = aspect
        super().__init__(*args, **kwargs)
        self.fields["skill_node"].queryset = SkillNode.objects.filter(
            tree__module=aspect.scheme.standard_module,
            node_type=SkillNode.NodeType.SKILL,
            is_active=True,
        ).select_related("tree").order_by("-tree__is_current", "tree__version", "sort_order", "code")
        self.fields["skill_node"].label = "技能点"
        self.fields["skill_node"].label_from_instance = lambda obj: f"{obj.tree.version} / {obj.code} - {obj.name}"

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.aspect = self.aspect
        if commit:
            instance.save()
            self.save_m2m()
        return instance
