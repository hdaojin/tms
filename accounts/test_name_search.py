from django.contrib.auth import get_user_model
from django.test import TestCase

from accounts.models import UserProfile
from accounts.services.users import (
    annotate_identity_labels, get_user_display_name, require_distinguishable_users, user_name_search_ids,
)
from django.core.exceptions import ValidationError


class NameSearchTests(TestCase):
    def test_name_pinyin_and_initials_do_not_search_login(self):
        user = get_user_model().objects.create_user("private-login", last_name="张", first_name="三")
        queryset = get_user_model().objects.prefetch_related("groups")
        for query in ("张三", "Zhang San", "zs"):
            self.assertIn(user.pk, user_name_search_ids(queryset, query))
        self.assertNotIn(user.pk, user_name_search_ids(queryset, "private-login"))

    def test_manual_pronunciation_takes_precedence_and_empty_name_is_private(self):
        user = get_user_model().objects.create_user("secret-id", last_name="单", first_name="明")
        UserProfile.objects.create(user=user, name_pronunciation="shan ming")
        self.assertIn(user.pk, user_name_search_ids(get_user_model().objects.all(), "shanming"))
        self.assertIn(user.pk, user_name_search_ids(get_user_model().objects.all(), "sm"))
        user.profile.name_pronunciation = "shanming"
        user.profile.save(update_fields=["name_pronunciation"])
        self.assertIn(user.pk, user_name_search_ids(get_user_model().objects.all(), "sm"))
        unnamed = get_user_model().objects.create_user("hidden-id")
        self.assertEqual(get_user_display_name(unnamed), "未填写姓名")

    def test_names_are_disambiguated_only_within_visible_scope(self):
        first = get_user_model().objects.create_user("private-one", last_name="张", first_name="三")
        second = get_user_model().objects.create_user("private-two", last_name="张", first_name="三")
        visible = get_user_model().objects.filter(pk__in=[first.pk, second.pk])
        with self.assertRaises(ValidationError):
            require_distinguishable_users(visible, [first.pk])
        UserProfile.objects.create(user=first, name_disambiguation="甲组")
        UserProfile.objects.create(user=second, name_disambiguation="乙组")
        labels = {person.pk: get_user_display_name(person) for person in annotate_identity_labels(visible)}
        self.assertEqual(labels[first.pk], "张三（甲组）")
        self.assertEqual(labels[second.pk], "张三（乙组）")
        single = annotate_identity_labels(visible.filter(pk=first.pk)).get()
        self.assertEqual(get_user_display_name(single), "张三")
