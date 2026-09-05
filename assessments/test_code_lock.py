from django.contrib import admin
from django.core.exceptions import ValidationError
from django.test import RequestFactory, TestCase

from standards.forms import SkillProjectForm

from .forms import AssessmentForm, AssessmentModuleForm
from .test_document_uploads import UploadFixture


class CodeLockTests(UploadFixture, TestCase):
    def test_code_is_immutable_before_any_document_exists_but_name_can_change(self):
        for instance in (self.assessment, self.project, self.module):
            original = instance.code
            instance.code = "NEWCODE"
            with self.subTest(model=type(instance).__name__):
                with self.assertRaisesMessage(ValidationError, "代码创建后不可修改"):
                    instance.clean()
                with self.assertRaisesMessage(ValidationError, "代码创建后不可修改"):
                    instance.save()
                instance.refresh_from_db()
                self.assertEqual(instance.code, original)
                instance.name = "新名称"
                instance.save()
                instance.refresh_from_db()
                self.assertEqual(instance.name, "新名称")

    def test_forms_disable_existing_codes_and_ignore_forged_post(self):
        for form_class, instance in (
            (AssessmentForm, self.assessment),
            (SkillProjectForm, self.project),
            (AssessmentModuleForm, self.module),
        ):
            with self.subTest(form=form_class.__name__):
                create = form_class()
                self.assertFalse(create.fields["code"].disabled)
                self.assertIn("请确认后保存", create.fields["code"].help_text)
                edit = form_class(instance=instance, data={"code": "FORGED"})
                self.assertTrue(edit.fields["code"].disabled)
                edit.is_valid()
                self.assertEqual(edit.cleaned_data["code"], instance.code)

    def test_admin_uses_same_code_lock_for_all_three_models(self):
        request = RequestFactory().get("/admin/")
        request.user = self.user
        for instance in (self.assessment, self.project, self.module):
            model_admin = admin.site._registry[type(instance)]
            create = model_admin.get_form(request)()
            edit = model_admin.get_form(request, instance)(instance=instance, data={"code": "FORGED"})
            with self.subTest(model=type(instance).__name__):
                self.assertIn("请确认后保存", create.fields["code"].help_text)
                self.assertTrue(edit.fields["code"].disabled)
                edit.is_valid()
                self.assertEqual(edit.cleaned_data["code"], instance.code)
