import random

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from standards.models import SkillProject

from glossary.forms import GlossaryEntryProposalForm
from glossary.models import GlossaryEntry, GlossaryEntryProposal, ProfessionalGlossary, StudyAttempt, StudySession
from glossary.services import (
    accepted_answers,
    approve_proposal,
    current_or_next_attempt,
    reject_proposal,
    submit_attempt,
)


class GlossaryTestCase(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="learner", password="test")
        self.other = get_user_model().objects.create_user(username="other", password="test")
        self.manager = get_user_model().objects.create_user(username="manager", password="test")
        project = SkillProject.objects.create(code="39", name="信息网络布线")
        self.glossary = ProfessionalGlossary.objects.create(skill_project=project, name="WSC 2026")
        self.entries = [
            GlossaryEntry.objects.create(
                glossary=self.glossary,
                english_term="Open Systems Interconnection",
                acronym="OSI",
                chinese_translation="开放系统互连（OSI）",
                english_aliases=["OSI model"],
                chinese_aliases=["开放式系统互联"],
            ),
            GlossaryEntry.objects.create(glossary=self.glossary, english_term="Router", chinese_translation="路由器"),
            GlossaryEntry.objects.create(glossary=self.glossary, english_term="Switch", chinese_translation="交换机"),
            GlossaryEntry.objects.create(glossary=self.glossary, english_term="Cable", chinese_translation="电缆"),
        ]


class StudyServiceTests(GlossaryTestCase):
    def test_acronym_explicit_alias_and_generated_chinese_alias_are_accepted(self):
        entry = self.entries[0]

        self.assertEqual(
            accepted_answers(entry, StudyAttempt.Direction.ZH_TO_EN),
            ["Open Systems Interconnection", "OSI", "OSI model"],
        )
        self.assertIn("开放系统互连", accepted_answers(entry, StudyAttempt.Direction.EN_TO_ZH))

    def test_submit_is_exact_after_normalization_and_idempotent(self):
        session = StudySession.objects.create(
            user=self.user,
            glossary=self.glossary,
            mode=StudySession.Mode.ZH_TO_EN,
            target_count=10,
        )
        attempt = StudyAttempt.objects.create(
            session=session,
            entry=self.entries[0],
            sequence=1,
            direction=StudyAttempt.Direction.ZH_TO_EN,
            prompt_snapshot="开放系统互连（OSI）",
            expected_answers_snapshot=accepted_answers(self.entries[0], StudyAttempt.Direction.ZH_TO_EN),
        )

        first = submit_attempt(attempt, "  osi\u00a0 ")
        second = submit_attempt(attempt, "wrong")

        self.assertTrue(first.is_correct)
        self.assertTrue(second.is_correct)
        self.assertEqual(second.submitted_answer, "osi")

    def test_mixed_mode_balances_directions_and_never_has_three_in_a_row(self):
        session = StudySession.objects.create(
            user=self.user,
            glossary=self.glossary,
            mode=StudySession.Mode.MIXED,
            target_count=10,
        )
        rng = random.Random(7)
        directions = []
        for _index in range(10):
            attempt = current_or_next_attempt(session, rng=rng)
            directions.append(attempt.direction)
            submit_attempt(attempt, "不会")
        self.assertIsNone(current_or_next_attempt(session, rng=rng))
        session.refresh_from_db()

        self.assertEqual(directions.count(StudyAttempt.Direction.EN_TO_ZH), 5)
        self.assertEqual(directions.count(StudyAttempt.Direction.ZH_TO_EN), 5)
        self.assertFalse(any(directions[index] == directions[index + 1] == directions[index + 2] for index in range(8)))
        self.assertEqual(session.status, StudySession.Status.COMPLETED)

    def test_unanswered_attempt_is_restored_and_does_not_count(self):
        session = StudySession.objects.create(
            user=self.user,
            glossary=self.glossary,
            mode=StudySession.Mode.EN_TO_ZH,
            target_count=10,
        )
        first = current_or_next_attempt(session, rng=random.Random(1))
        resumed = current_or_next_attempt(session, rng=random.Random(2))

        self.assertEqual(first.pk, resumed.pk)
        self.assertEqual(session.answered_count, 0)


class ProposalAndPermissionTests(GlossaryTestCase):
    def _grant(self, user, *codenames):
        user.user_permissions.add(*Permission.objects.filter(content_type__app_label="glossary", codename__in=codenames))

    def test_proposal_duplicate_is_checked_and_rejection_requires_reason(self):
        form = GlossaryEntryProposalForm(
            data={
                "glossary": self.glossary.pk,
                "english_term": " router ",
                "acronym": "",
                "chinese_translation": "路由设备",
                "english_aliases_text": "",
                "chinese_aliases_text": "",
            },
            user=self.user,
        )
        self.assertFalse(form.is_valid())
        proposal = GlossaryEntryProposal.objects.create(
            glossary=self.glossary,
            english_term="Firewall",
            chinese_translation="防火墙",
            submitted_by=self.user,
        )
        with self.assertRaisesMessage(ValidationError, "必须填写原因"):
            reject_proposal(proposal, user=self.manager, note=" ")

        reject_proposal(proposal, user=self.manager, note="释义需要补充")
        proposal.refresh_from_db()
        self.assertEqual(proposal.status, GlossaryEntryProposal.Status.REJECTED)

    def test_approval_creates_official_entry_and_preserves_submitter(self):
        proposal = GlossaryEntryProposal.objects.create(
            glossary=self.glossary,
            english_term="Firewall",
            chinese_translation="防火墙",
            submitted_by=self.user,
        )

        entry = approve_proposal(proposal, user=self.manager, note="通过")

        proposal.refresh_from_db()
        self.assertEqual(entry.created_by, self.user)
        self.assertEqual(entry.updated_by, self.manager)
        self.assertEqual(proposal.resulting_entry, entry)
        self.assertEqual(proposal.status, GlossaryEntryProposal.Status.APPROVED)

    def test_login_browse_and_owner_statistics_boundaries(self):
        self.assertEqual(self.client.get(reverse("glossary:browse")).status_code, 302)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("glossary:browse")).status_code, 200)
        self.assertEqual(self.client.get(reverse("glossary:my_stats")).status_code, 200)
        self.assertEqual(self.client.get(reverse("glossary:all_stats")).status_code, 403)

        other_session = StudySession.objects.create(
            user=self.other,
            glossary=self.glossary,
            mode=StudySession.Mode.EN_TO_ZH,
            target_count=10,
        )
        self.assertEqual(
            self.client.get(reverse("glossary:session_summary", args=[other_session.pk])).status_code,
            404,
        )

    def test_contributor_only_sees_own_proposals_and_manager_can_see_all(self):
        own = GlossaryEntryProposal.objects.create(
            glossary=self.glossary,
            english_term="Firewall",
            chinese_translation="防火墙",
            submitted_by=self.user,
        )
        other = GlossaryEntryProposal.objects.create(
            glossary=self.glossary,
            english_term="Server",
            chinese_translation="服务器",
            submitted_by=self.other,
        )
        self._grant(self.user, "view_glossaryentryproposal", "add_glossaryentryproposal", "change_glossaryentryproposal")
        self.client.force_login(self.user)

        response = self.client.get(reverse("glossary:proposal_list"))
        self.assertContains(response, own.english_term)
        self.assertNotContains(response, other.english_term)

        self._grant(self.manager, "change_professionalglossary", "view_glossaryentryproposal")
        self.client.force_login(self.manager)
        response = self.client.get(reverse("glossary:proposal_list"))
        self.assertContains(response, own.english_term)
        self.assertContains(response, other.english_term)
