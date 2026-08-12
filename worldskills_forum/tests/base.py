from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.utils import timezone

from worldskills_forum.models import ForumCategory, ForumModule, ForumPost, ForumTag, ForumTopic, ForumTranslation


class ForumTestCase(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.reader = user_model.objects.create_user(username="reader", password="test")
        self.translator_a = user_model.objects.create_user(username="translator_a", password="test")
        self.translator_b = user_model.objects.create_user(username="translator_b", password="test")
        self.manager = user_model.objects.create_user(username="manager", password="test")
        self.superuser = user_model.objects.create_superuser(username="root", password="test", email="root@example.com")
        self.category = ForumCategory.objects.create(name="评分测试", slug="marking-test")
        self.module = ForumModule.objects.get(slug="module-d")
        self.tag = ForumTag.objects.create(name="Linux", slug="linux")
        self.grant(self.translator_a, "add_forumtopic", "add_forumpost", "add_forumtranslation")
        self.grant(self.translator_b, "add_forumtopic", "add_forumpost", "add_forumtranslation")
        self.grant(
            self.manager,
            "change_forumtopic", "change_forumpost", "change_forumtranslation",
            "delete_forumtopic", "delete_forumpost", "delete_forumtranslation",
        )

    def grant(self, user, *codenames):
        user.user_permissions.add(*Permission.objects.filter(content_type__app_label="worldskills_forum", codename__in=codenames))

    def make_topic(self, user=None, **kwargs):
        data = {
            "competition_year": 2026,
            "translated_title": "模块 D 主观评分讨论",
            "original_title": "Module D Marking Discussion",
            "source_url": "https://forum.example.com/t/100",
            "module": self.module,
            "category": self.category,
            "importance": "important",
            "created_by": user or self.translator_a,
            "updated_by": user or self.translator_a,
        }
        data.update(kwargs)
        topic = ForumTopic.objects.create(**data)
        topic.tags.add(self.tag)
        return topic

    def make_post(self, topic=None, user=None, published_at=None, posted_at=None, **kwargs):
        topic = topic or self.make_topic(user=user)
        user = user or self.translator_a
        data = {
            "topic": topic,
            "author_name": "Expert A",
            "source_role": "expert",
            "posted_at": posted_at or timezone.now() - timedelta(days=2),
            "source_url": "https://forum.example.com/p/101",
            "post_type": "discussion",
            "importance": "normal",
            "original_content": "Original marking guidance",
            "created_by": user,
            "updated_by": user,
        }
        data.update(kwargs)
        post = ForumPost.objects.create(**data)
        ForumTranslation.objects.create(
            post=post,
            translated_content="中文评分说明",
            translated_by=user,
            updated_by=user,
            published_at=published_at or timezone.now(),
        )
        return post
