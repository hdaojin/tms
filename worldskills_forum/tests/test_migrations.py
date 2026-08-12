from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone


class EditableSourceRoleMigrationTests(TransactionTestCase):
    migrate_from = ("worldskills_forum", "0003_editable_forum_modules")
    migrate_to = (
        "worldskills_forum",
        "0004_forumsourcerole_alter_forumpost_source_role_detail_and_more",
    )

    def setUp(self):
        super().setUp()
        self.executor = MigrationExecutor(connection)
        self.executor.migrate([self.migrate_from])
        old_apps = self.executor.loader.project_state([self.migrate_from]).apps
        category_model = old_apps.get_model("worldskills_forum", "ForumCategory")
        module_model = old_apps.get_model("worldskills_forum", "ForumModule")
        topic_model = old_apps.get_model("worldskills_forum", "ForumTopic")
        post_model = old_apps.get_model("worldskills_forum", "ForumPost")
        category = category_model.objects.create(name="迁移测试", slug="migration-test")
        topic = topic_model.objects.create(
            competition_year=2026,
            translated_title="来源身份迁移",
            original_title="Source role migration",
            source_url="https://forum.example.com/t/migration",
            module=module_model.objects.get(slug="module-d"),
            category=category,
            importance="normal",
        )
        self.post_pk = post_model.objects.create(
            topic=topic,
            author_name="Expert A",
            source_role="expert",
            posted_at=timezone.now(),
            post_type="discussion",
            importance="normal",
            original_content="Migration content",
        ).pk

    def tearDown(self):
        self.executor = MigrationExecutor(connection)
        self.executor.migrate([self.migrate_to])
        super().tearDown()

    def test_forward_and_reverse_preserve_existing_source_role(self):
        self.executor = MigrationExecutor(connection)
        self.executor.migrate([self.migrate_to])
        new_apps = self.executor.loader.project_state([self.migrate_to]).apps
        role_model = new_apps.get_model("worldskills_forum", "ForumSourceRole")
        post_model = new_apps.get_model("worldskills_forum", "ForumPost")

        post = post_model.objects.select_related("source_role").get(pk=self.post_pk)
        self.assertEqual(post.source_role.slug, "expert")
        self.assertTrue(role_model.objects.get(slug="worldskills_official").is_official)
        self.assertTrue(role_model.objects.get(slug="other").allows_detail)

        self.executor = MigrationExecutor(connection)
        self.executor.migrate([self.migrate_from])
        old_apps = self.executor.loader.project_state([self.migrate_from]).apps
        old_post_model = old_apps.get_model("worldskills_forum", "ForumPost")
        self.assertEqual(old_post_model.objects.get(pk=self.post_pk).source_role, "expert")
