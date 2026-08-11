from __future__ import annotations

import hashlib
import random
from collections import defaultdict
from typing import BinaryIO

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from .models import (
    GlossaryEntry,
    GlossaryEntryProposal,
    GlossaryImport,
    ProfessionalGlossary,
    StudyAttempt,
    StudySession,
)
from .normalization import generated_chinese_alias, normalized_answer, unique_normalized
from .parser import GlossaryWorkbookError, parse_smartcat_workbook


def calculate_sha256(file_obj: BinaryIO) -> str:
    try:
        position = file_obj.tell()
    except (AttributeError, OSError):
        position = None
    file_obj.seek(0)
    digest = hashlib.sha256()
    for chunk in iter(lambda: file_obj.read(1024 * 1024), b""):
        digest.update(chunk)
    file_obj.seek(position or 0)
    return digest.hexdigest()


def _entry_snapshot(entry: GlossaryEntry) -> dict:
    return {
        "id": entry.pk,
        "english_term": entry.english_term,
        "acronym": entry.acronym,
        "chinese_translation": entry.chinese_translation,
        "english_aliases": entry.english_aliases,
        "chinese_aliases": entry.chinese_aliases,
        "is_active": entry.is_active,
        "updated_at": entry.updated_at.isoformat(),
    }


def create_glossary_import(glossary, uploaded_file, *, user) -> GlossaryImport:
    sha256 = calculate_sha256(uploaded_file)
    status = GlossaryImport.Status.PREVIEW
    try:
        parsed_payload = parse_smartcat_workbook(uploaded_file)
    except GlossaryWorkbookError as exc:
        parsed_payload = {
            "sheet_name": "",
            "groups": [],
            "warnings": [],
            "errors": exc.errors,
            "counts": {
                "source_rows": 0,
                "unique_terms": 0,
                "identical_duplicates": 0,
                "conflicting_duplicates": 0,
            },
        }
        status = GlossaryImport.Status.INVALID
    keys = [group["english_key"] for group in parsed_payload["groups"]]
    existing = {
        entry.english_key: entry
        for entry in GlossaryEntry.objects.filter(glossary=glossary, english_key__in=keys)
    }
    pending_by_key: dict[str, list[dict]] = defaultdict(list)
    for proposal in GlossaryEntryProposal.objects.filter(
        glossary=glossary,
        status=GlossaryEntryProposal.Status.PENDING,
        english_key__in=keys,
    ).select_related("submitted_by"):
        pending_by_key[proposal.english_key].append(
            {"id": proposal.pk, "english_term": proposal.english_term, "submitted_by": str(proposal.submitted_by)}
        )
    for group in parsed_payload["groups"]:
        entry = existing.get(group["english_key"])
        group["existing"] = _entry_snapshot(entry) if entry else None
        group["pending_proposals"] = pending_by_key.get(group["english_key"], [])

    glossary.refresh_from_db(fields=["updated_at"])
    uploaded_file.seek(0)
    return GlossaryImport.objects.create(
        glossary=glossary,
        source_file=uploaded_file,
        original_filename=uploaded_file.name,
        sha256=sha256,
        status=status,
        parsed_payload=parsed_payload,
        glossary_version=glossary.updated_at,
        imported_by=user,
    )


def confirm_glossary_import(glossary_import: GlossaryImport, decisions: dict, *, user) -> GlossaryImport:
    confirmed = _confirm_glossary_import_locked(glossary_import, decisions, user=user)
    if confirmed is None:
        raise ValidationError("词库在预览后已发生变化，请重新上传并确认。")
    return confirmed


@transaction.atomic
def _confirm_glossary_import_locked(
    glossary_import: GlossaryImport,
    decisions: dict,
    *,
    user,
) -> GlossaryImport | None:
    locked_import = GlossaryImport.objects.select_for_update().select_related("glossary").get(pk=glossary_import.pk)
    if locked_import.status != GlossaryImport.Status.PREVIEW:
        raise ValidationError("该导入记录已确认或已过期。")
    glossary = ProfessionalGlossary.objects.select_for_update().get(pk=locked_import.glossary_id)
    if glossary.updated_at != locked_import.glossary_version:
        locked_import.status = GlossaryImport.Status.STALE
        locked_import.save(update_fields=["status"])
        return None

    groups = locked_import.parsed_payload.get("groups", [])
    keys = [group["english_key"] for group in groups]
    existing = {
        entry.english_key: entry
        for entry in GlossaryEntry.objects.select_for_update().filter(glossary=glossary, english_key__in=keys)
    }
    pending_keys = set(
        GlossaryEntryProposal.objects.filter(
            glossary=glossary,
            status=GlossaryEntryProposal.Status.PENDING,
            english_key__in=keys,
        ).values_list("english_key", flat=True)
    )

    created = 0
    overwritten = 0
    skipped = 0
    audit_rows: list[dict] = []
    overwrite_all = bool(decisions.get("overwrite_all"))
    for index, group in enumerate(groups):
        options = group.get("options") or []
        choice = decisions.get("choices", {}).get(str(index))
        if len(options) > 1 and choice is None:
            raise ValidationError(f"重复组 {index + 1} 尚未选择保留行。")
        choice = 0 if choice is None else choice
        try:
            selected = options[int(choice)]
        except (IndexError, TypeError, ValueError) as exc:
            raise ValidationError(f"重复组 {index + 1} 尚未选择保留行。") from exc

        key = group["english_key"]
        entry = existing.get(key)
        before = _entry_snapshot(entry) if entry else None
        if key in pending_keys:
            skipped += 1
            audit_rows.append({"action": "pending_skipped", "source": selected, "before": before, "after": before})
            continue
        should_overwrite = overwrite_all or str(index) in set(decisions.get("overwrite", []))
        if entry is not None and not should_overwrite:
            skipped += 1
            audit_rows.append({"action": "skipped", "source": selected, "before": before, "after": before})
            continue

        if entry is None:
            entry = GlossaryEntry(
                glossary=glossary,
                source=GlossaryEntry.Source.IMPORT,
                is_active=True,
                created_by=user,
            )
            created += 1
            action = "created"
        else:
            overwritten += 1
            action = "overwritten"
        entry.english_term = selected["english_term"]
        entry.acronym = selected["acronym"]
        entry.chinese_translation = selected["chinese_translation"]
        entry.updated_by = user
        entry.save()
        existing[key] = entry
        audit_rows.append({"action": action, "source": selected, "before": before, "after": _entry_snapshot(entry)})

    locked_import.status = GlossaryImport.Status.CONFIRMED
    locked_import.decision_payload = decisions
    locked_import.result_summary = {
        "created": created,
        "overwritten": overwritten,
        "skipped": skipped,
        "rows": audit_rows,
    }
    locked_import.confirmed_at = timezone.now()
    locked_import.save(update_fields=["status", "decision_payload", "result_summary", "confirmed_at"])
    return locked_import


@transaction.atomic
def approve_proposal(proposal: GlossaryEntryProposal, *, user, note: str = "") -> GlossaryEntry:
    proposal = GlossaryEntryProposal.objects.select_for_update().get(pk=proposal.pk)
    if proposal.status != GlossaryEntryProposal.Status.PENDING:
        raise ValidationError("只能审核待审核提案。")
    if GlossaryEntry.objects.filter(glossary=proposal.glossary, english_key=proposal.english_key).exists():
        raise ValidationError("词库中已存在相同英文词条，不能通过该提案。")
    entry = GlossaryEntry.objects.create(
        glossary=proposal.glossary,
        english_term=proposal.english_term,
        acronym=proposal.acronym,
        chinese_translation=proposal.chinese_translation,
        english_aliases=proposal.english_aliases,
        chinese_aliases=proposal.chinese_aliases,
        source=GlossaryEntry.Source.PROPOSAL,
        created_by=proposal.submitted_by,
        updated_by=user,
    )
    proposal.status = GlossaryEntryProposal.Status.APPROVED
    proposal.reviewed_by = user
    proposal.reviewed_at = timezone.now()
    proposal.review_note = note
    proposal.resulting_entry = entry
    proposal.save(update_fields=["status", "reviewed_by", "reviewed_at", "review_note", "resulting_entry", "updated_at"])
    return entry


@transaction.atomic
def reject_proposal(proposal: GlossaryEntryProposal, *, user, note: str) -> None:
    proposal = GlossaryEntryProposal.objects.select_for_update().get(pk=proposal.pk)
    if not note.strip():
        raise ValidationError("驳回提案时必须填写原因。")
    if proposal.status != GlossaryEntryProposal.Status.PENDING:
        raise ValidationError("只能审核待审核提案。")
    proposal.status = GlossaryEntryProposal.Status.REJECTED
    proposal.reviewed_by = user
    proposal.reviewed_at = timezone.now()
    proposal.review_note = note.strip()
    proposal.save(update_fields=["status", "reviewed_by", "reviewed_at", "review_note", "updated_at"])


def accepted_answers(entry: GlossaryEntry, direction: str) -> list[str]:
    if direction == StudyAttempt.Direction.ZH_TO_EN:
        return unique_normalized(
            [entry.english_term, entry.acronym, *(entry.english_aliases or [])],
            english=True,
        )
    generated_alias = generated_chinese_alias(entry.chinese_translation, entry.english_term, entry.acronym)
    return unique_normalized(
        [entry.chinese_translation, generated_alias, *(entry.chinese_aliases or [])],
        english=False,
    )


def _choose_direction(session: StudySession, rng: random.Random) -> str:
    if session.mode != StudySession.Mode.MIXED:
        return session.mode
    answered = list(
        session.attempts.filter(answered_at__isnull=False).order_by("-sequence").values_list("direction", flat=True)
    )
    if len(answered) >= 2 and answered[0] == answered[1]:
        return (
            StudyAttempt.Direction.ZH_TO_EN
            if answered[0] == StudyAttempt.Direction.EN_TO_ZH
            else StudyAttempt.Direction.EN_TO_ZH
        )
    en_count = answered.count(StudyAttempt.Direction.EN_TO_ZH)
    zh_count = len(answered) - en_count
    if en_count > zh_count:
        return StudyAttempt.Direction.ZH_TO_EN
    if zh_count > en_count:
        return StudyAttempt.Direction.EN_TO_ZH
    return rng.choice([StudyAttempt.Direction.EN_TO_ZH, StudyAttempt.Direction.ZH_TO_EN])


def _choose_entry(session: StudySession, direction: str, rng: random.Random) -> GlossaryEntry:
    entries = list(GlossaryEntry.objects.filter(glossary=session.glossary, is_active=True).order_by("pk"))
    if not entries:
        raise ValidationError("该词库当前没有可学习词条。")

    stats_rows = (
        StudyAttempt.objects.filter(
            session__user=session.user,
            session__glossary=session.glossary,
            direction=direction,
            answered_at__isnull=False,
        )
        .values("entry_id")
        .annotate(total=Count("id"), wrong=Count("id", filter=Q(is_correct=False)))
    )
    stats = {row["entry_id"]: row for row in stats_rows}
    recent_ids = list(
        session.attempts.filter(answered_at__isnull=False)
        .order_by("-sequence")
        .values_list("entry_id", flat=True)[:2]
    )
    next_number = session.attempts.filter(answered_at__isnull=False).count() + 1
    review_slot = next_number % 4 == 0
    if review_slot:
        candidates = [entry for entry in entries if stats.get(entry.pk, {}).get("wrong", 0) > 0]
    else:
        candidates = []
    if not candidates:
        min_total = min(stats.get(entry.pk, {}).get("total", 0) for entry in entries)
        candidates = [entry for entry in entries if stats.get(entry.pk, {}).get("total", 0) == min_total]
        review_slot = False

    without_recent = [entry for entry in candidates if entry.pk not in recent_ids]
    if without_recent:
        candidates = without_recent
    if not review_slot:
        return rng.choice(candidates)
    weights = []
    for entry in candidates:
        total = stats[entry.pk]["total"]
        wrong = stats[entry.pk]["wrong"]
        weights.append(1 + 4 * ((wrong + 1) / (total + 2)))
    return rng.choices(candidates, weights=weights, k=1)[0]


@transaction.atomic
def current_or_next_attempt(session: StudySession, *, rng: random.Random | None = None) -> StudyAttempt | None:
    session = StudySession.objects.select_for_update().select_related("glossary", "user").get(pk=session.pk)
    if session.status != StudySession.Status.ACTIVE:
        return None
    unanswered = session.attempts.filter(answered_at__isnull=True).order_by("sequence").first()
    if unanswered:
        return unanswered
    answered_count = session.attempts.filter(answered_at__isnull=False).count()
    if session.target_count is not None and answered_count >= session.target_count:
        session.status = StudySession.Status.COMPLETED
        session.ended_at = timezone.now()
        session.save(update_fields=["status", "ended_at"])
        return None
    rng = rng or random.SystemRandom()
    direction = _choose_direction(session, rng)
    entry = _choose_entry(session, direction, rng)
    prompt = entry.chinese_translation
    if direction == StudyAttempt.Direction.EN_TO_ZH:
        prompt = entry.english_term
        if entry.acronym and entry.acronym.casefold() != entry.english_term.casefold():
            prompt = f"{prompt} ({entry.acronym})"
    return StudyAttempt.objects.create(
        session=session,
        entry=entry,
        sequence=answered_count + 1,
        direction=direction,
        prompt_snapshot=prompt,
        expected_answers_snapshot=accepted_answers(entry, direction),
    )


@transaction.atomic
def submit_attempt(attempt: StudyAttempt, answer: str) -> StudyAttempt:
    attempt = StudyAttempt.objects.select_for_update().select_related("session").get(pk=attempt.pk)
    if attempt.answered_at is not None:
        return attempt
    if attempt.session.status != StudySession.Status.ACTIVE:
        raise ValidationError("该学习会话已经结束。")
    english = attempt.direction == StudyAttempt.Direction.ZH_TO_EN
    cleaned_answer = normalized_answer(answer, english=english)
    accepted = {
        normalized_answer(value, english=english)
        for value in attempt.expected_answers_snapshot
    }
    attempt.submitted_answer = answer.strip()
    attempt.normalized_submitted_answer = cleaned_answer
    attempt.is_correct = cleaned_answer in accepted and bool(cleaned_answer)
    attempt.answered_at = timezone.now()
    attempt.save(
        update_fields=[
            "submitted_answer",
            "normalized_submitted_answer",
            "is_correct",
            "answered_at",
        ]
    )
    return attempt


def stop_session(session: StudySession) -> StudySession:
    if session.status == StudySession.Status.ACTIVE:
        session.status = StudySession.Status.STOPPED
        session.ended_at = timezone.now()
        session.save(update_fields=["status", "ended_at"])
    return session
