from django.db import migrations


def preserve_facts(apps, schema_editor):
    Execution = apps.get_model("training", "TaskExecution")
    Progress = apps.get_model("training", "TrainingProgress")
    Feedback = apps.get_model("training", "TrainingCoachFeedback")
    Coach = apps.get_model("training", "TrainingAssignmentCoach")
    Participant = apps.get_model("training", "TrainingPlanParticipant")
    for execution in Execution.objects.using(schema_editor.connection.alias).select_related("training_task").iterator():
        alias = schema_editor.connection.alias
        Execution.objects.using(alias).filter(pk=execution.pk).update(legacy_status=execution.status)
        Participant.objects.using(alias).get_or_create(training_plan_id=execution.training_task.training_plan_id, user_id=execution.user_id, defaults={"is_active": False, "was_initial": False})
        completed = "\n\n".join(filter(None, [execution.completion_note, execution.solution, execution.reflection]))
        if completed or execution.problems:
            Progress.objects.using(alias).create(execution_id=execution.pk, author_id=execution.user_id, completed=completed, problems=execution.problems, is_legacy=True)
        if execution.coach_feedback and execution.feedback_by_id:
            Feedback.objects.using(alias).create(execution_id=execution.pk, author_id=execution.feedback_by_id, content=execution.coach_feedback, recorded_at=execution.feedback_at or execution.updated_at, is_legacy=True)
        for coach_id in execution.training_task.coach_links.values_list("user_id", flat=True):
            Coach.objects.using(alias).get_or_create(execution_id=execution.pk, user_id=coach_id)


class Migration(migrations.Migration):
    dependencies = [("training", "0011_training_process_and_slot_times")]
    # 新系统会追加旧结构无法表达的历史，不能通过反向迁移无痕丢弃。
    operations = [migrations.RunPython(preserve_facts, reverse_code=migrations.RunPython.noop)]
