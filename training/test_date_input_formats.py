from datetime import date, datetime

from django.test import TestCase
from django.utils import timezone, translation

from assessments.forms import AssessmentModuleForm
from behaviors.forms import ConductRecordForm
from glossary.forms import StatisticsFilterForm
from meetings.forms import MeetingUploadForm
from training.forms import TrainingPlanForm, TrainingTaskForm


class DateInputFormatTests(TestCase):
    def test_date_fields_render_standard_browser_values(self):
        cases = (
            (TrainingPlanForm, ("start_date", "end_date")),
            (TrainingTaskForm, ("planned_date",)),
            (ConductRecordForm, ("occurred_date",)),
            (MeetingUploadForm, ("date",)),
            (StatisticsFilterForm, ("date_from", "date_to")),
        )
        with translation.override("zh-hans"):
            for form_class, fields in cases:
                with self.subTest(form=form_class.__name__):
                    form = form_class(initial={field: date(2026, 1, 2) for field in fields})
                    for field in fields:
                        self.assertIn('value="2026-01-02"', str(form[field]))

    def test_module_datetime_renders_local_time_with_seconds_and_accepts_it(self):
        with translation.override("zh-hans"), timezone.override("Asia/Shanghai"):
            value = timezone.make_aware(datetime(2026, 1, 2, 13, 14, 15))
            form = AssessmentModuleForm(initial={"scheduled_start_at": value})
            self.assertIn('value="2026-01-02T13:14:15"', str(form["scheduled_start_at"]))
            self.assertIn('step="1"', str(form["scheduled_start_at"]))
            self.assertEqual(form.fields["scheduled_start_at"].clean("2026-01-02T13:14:15"), value)
