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
        module, _created = module_model.objects.get_or_create(
            slug="module-d",
            defaults={"name": "模块 D"},
        )
        topic = topic_model.objects.create(
            competition_year=2026,
            translated_title="来源身份迁移",
            original_title="Source role migration",
            source_url="https://forum.example.com/t/migration",
            module=module,
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
        self.executor.migrate(self.executor.loader.graph.leaf_nodes())
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


class ForumPostTypeMigrationTests(TransactionTestCase):
    migrate_from = ('worldskills_forum', '0005_alter_forumtopic_options')
    migrate_to = ('worldskills_forum', '0008_finalize_forum_post_type')

    @staticmethod
    def targets(executor, target):
        return [
            *[node for node in executor.loader.graph.leaf_nodes() if node[0] != 'worldskills_forum'],
            target,
        ]

    def setUp(self):
        super().setUp()
        executor = MigrationExecutor(connection)
        from_targets = self.targets(executor, self.migrate_from)
        executor.migrate(from_targets)
        old_apps = executor.loader.project_state(from_targets).apps
        User = old_apps.get_model('auth', 'User')
        ForumCategory = old_apps.get_model('worldskills_forum', 'ForumCategory')
        ForumModule = old_apps.get_model('worldskills_forum', 'ForumModule')
        ForumPost = old_apps.get_model('worldskills_forum', 'ForumPost')
        ForumSourceRole = old_apps.get_model('worldskills_forum', 'ForumSourceRole')
        ForumTopic = old_apps.get_model('worldskills_forum', 'ForumTopic')

        user = User.objects.create(username='forum-post-type-migration')
        category = ForumCategory.objects.create(name='类型迁移', slug='type-migration')
        module = ForumModule.objects.create(name='类型迁移模块', slug='type-migration-module')
        role, _created = ForumSourceRole.objects.get_or_create(
            slug='expert',
            defaults={'name': '专家'},
        )
        topic = ForumTopic.objects.create(
            competition_year=2026,
            translated_title='论坛类型迁移',
            original_title='Forum type migration',
            source_url='https://forum.example.com/t/type-migration',
            module=module,
            category=category,
            importance='normal',
            created_by=user,
            updated_by=user,
        )
        common = {
            'topic': topic,
            'author_name': 'Expert A',
            'source_role': role,
            'posted_at': timezone.now(),
            'importance': 'normal',
            'original_content': 'Migration content',
            'created_by': user,
            'updated_by': user,
        }
        self.known_pk = ForumPost.objects.create(post_type='official_reply', **common).pk
        self.unknown_pk = ForumPost.objects.create(post_type='legacy-post-type', **common).pk

        executor = MigrationExecutor(connection)
        to_targets = self.targets(executor, self.migrate_to)
        executor.migrate(to_targets)
        self.apps = executor.loader.project_state(to_targets).apps

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()

    def test_known_and_unknown_codes_survive_forward_and_reverse(self):
        ForumPost = self.apps.get_model('worldskills_forum', 'ForumPost')
        known = ForumPost.objects.get(pk=self.known_pk).post_type
        unknown = ForumPost.objects.get(pk=self.unknown_pk).post_type
        self.assertEqual(known.code, 'official_reply')
        self.assertTrue(known.is_official)
        self.assertEqual(unknown.code, 'legacy-post-type')
        self.assertFalse(unknown.is_active)

        executor = MigrationExecutor(connection)
        from_targets = self.targets(executor, self.migrate_from)
        executor.migrate(from_targets)
        old_apps = executor.loader.project_state(from_targets).apps
        OldForumPost = old_apps.get_model('worldskills_forum', 'ForumPost')
        self.assertEqual(OldForumPost.objects.get(pk=self.known_pk).post_type, 'official_reply')
        self.assertEqual(OldForumPost.objects.get(pk=self.unknown_pk).post_type, 'legacy-post-type')
